from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from stock.models import LotStock, MouvementStock

from .models import LigneVente, Paiement, RetourVente, Vente


class ServiceVente:
    """Logique atomique de validation, annulation et retour des ventes."""

    @staticmethod
    def _verifier_fefo(lignes_lots):
        """Refuse une sortie qui ignorerait un lot plus proche de la peremption."""
        quantites_par_lot = {}
        for ligne, lot in lignes_lots:
            quantites_par_lot[lot.pk] = quantites_par_lot.get(lot.pk, 0) + ligne.quantite

        for ligne, lot in lignes_lots:
            lots_anterieurs = LotStock.objects.filter(
                medicament=lot.medicament,
                est_bloque=False,
                date_peremption__gte=date.today(),
                quantite_disponible__gt=0,
            ).filter(
                Q(date_peremption__lt=lot.date_peremption)
                | Q(date_peremption=lot.date_peremption, date_reception__lt=lot.date_reception)
                | Q(
                    date_peremption=lot.date_peremption,
                    date_reception=lot.date_reception,
                    pk__lt=lot.pk,
                )
            )
            for anterieur in lots_anterieurs:
                restant = anterieur.quantite_disponible - quantites_par_lot.get(
                    anterieur.pk, 0
                )
                if restant > 0:
                    raise ValidationError(
                        "FEFO : le lot "
                        f"{anterieur.numero_lot} (peremption {anterieur.date_peremption:%d/%m/%Y}) "
                        "doit etre vendu en priorite."
                    )

    @staticmethod
    @transaction.atomic
    def valider_vente(vente, utilisateur=None):
        vente = Vente.objects.select_for_update().get(pk=vente.pk)
        if vente.statut == Vente.VALIDEE:
            raise ValidationError("Cette vente est deja validee (protection idempotente).")
        if vente.statut != Vente.EN_COURS:
            raise ValidationError("Cette vente ne peut plus etre validee.")

        lignes = list(
            vente.lignes.select_for_update().select_related("medicament", "lot")
        )
        if not lignes:
            raise ValidationError("Impossible de valider une vente sans ligne.")

        lignes_lots = []
        for ligne in lignes:
            if ligne.quantite is None or ligne.quantite <= 0:
                raise ValidationError("Les quantites vendues doivent etre strictement positives.")
            lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
            if lot.medicament_id != ligne.medicament_id:
                raise ValidationError("Le lot ne correspond pas au medicament de la ligne.")
            if lot.est_bloque:
                raise ValidationError(
                    f"Le lot {lot.numero_lot} est bloque et ne peut pas etre vendu."
                )
            if lot.est_perime():
                raise ValidationError(
                    f"Le lot {lot.numero_lot} est perime et ne peut pas etre vendu."
                )
            if ligne.quantite > lot.quantite_disponible:
                raise ValidationError(
                    f"Stock insuffisant pour {ligne.medicament} : "
                    f"disponible {lot.quantite_disponible}, demande {ligne.quantite}."
                )
            lignes_lots.append((ligne, lot))

        ServiceVente._verifier_fefo(lignes_lots)

        for ligne, lot in lignes_lots:
            lot.quantite_disponible -= ligne.quantite
            lot.save(update_fields=["quantite_disponible"])
            MouvementStock.enregistrer(
                lot,
                MouvementStock.SORTIE_VENTE,
                -ligne.quantite,
                utilisateur=utilisateur or vente.caissier,
                reference_type="Vente",
                reference_id=vente.pk,
                motif=f"Vente {vente.numero}",
            )

        vente.total = sum((ligne.sous_total() for ligne in lignes), start=Decimal("0"))
        vente.statut = Vente.VALIDEE
        vente.save(update_fields=["total", "statut"])
        return vente

    @staticmethod
    @transaction.atomic
    def annuler_vente(vente, motif, utilisateur=None):
        vente = Vente.objects.select_for_update().get(pk=vente.pk)
        if vente.statut == Vente.ANNULEE:
            raise ValidationError("Cette vente est deja annulee.")
        if vente.statut != Vente.VALIDEE:
            raise ValidationError("Seule une vente validee peut etre annulee.")
        if not motif or not motif.strip():
            raise ValidationError("Le motif d'annulation est obligatoire.")

        lignes = list(vente.lignes.select_related("lot"))
        for ligne in lignes:
            lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
            if lot.est_perime() or lot.est_bloque:
                continue
            lot.quantite_disponible += ligne.quantite
            lot.save(update_fields=["quantite_disponible"])
            MouvementStock.enregistrer(
                lot,
                MouvementStock.RETOUR,
                ligne.quantite,
                utilisateur=utilisateur or vente.caissier,
                reference_type="AnnulationVente",
                reference_id=vente.pk,
                motif=f"Annulation vente {vente.numero} : {motif}",
            )

        vente.statut = Vente.ANNULEE
        vente.motif_annulation = motif
        vente.save(update_fields=["statut", "motif_annulation"])
        vente.paiements.filter(statut=Paiement.CONFIRME).update(statut=Paiement.REMBOURSE)
        return vente

    @staticmethod
    @transaction.atomic
    def traiter_retour(retour, utilisateur=None):
        retour = RetourVente.objects.select_for_update().get(pk=retour.pk)
        if retour.est_valide:
            raise ValidationError("Ce retour a deja ete valide.")
        if retour.quantite_retournee is None or retour.quantite_retournee <= 0:
            raise ValidationError("La quantite retournee doit etre strictement positive.")
        if not retour.motif or not retour.motif.strip():
            raise ValidationError("Le motif du retour est obligatoire.")

        ligne = LigneVente.objects.select_for_update().get(pk=retour.ligne_vente_id)
        vente = Vente.objects.select_for_update().get(pk=ligne.vente_id)
        if vente.statut != Vente.VALIDEE:
            raise ValidationError("Seule une vente validee peut faire l'objet d'un retour.")

        deja_retournee = (
            RetourVente.objects.filter(ligne_vente=ligne, est_valide=True).aggregate(
                total=Sum("quantite_retournee")
            )["total"]
            or 0
        )
        if deja_retournee + retour.quantite_retournee > ligne.quantite:
            raise ValidationError(
                "La quantite retournee depasse la quantite vendue restante."
            )

        retour.montant_rembourse = ligne.prix_unitaire_applique * retour.quantite_retournee

        if retour.remis_en_stock and retour.est_eligible_remise_en_stock():
            lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
            lot.quantite_disponible += retour.quantite_retournee
            lot.save(update_fields=["quantite_disponible"])
            MouvementStock.enregistrer(
                lot,
                MouvementStock.RETOUR,
                retour.quantite_retournee,
                utilisateur=utilisateur or retour.utilisateur,
                reference_type="RetourVente",
                reference_id=retour.pk,
                motif=f"Retour vente {vente.numero} : {retour.motif}",
            )
        else:
            retour.remis_en_stock = False

        retour.est_valide = True
        retour.utilisateur = utilisateur or retour.utilisateur
        retour.save(
            update_fields=[
                "montant_rembourse",
                "remis_en_stock",
                "est_valide",
                "utilisateur",
            ]
        )
        return retour

    @staticmethod
    @transaction.atomic
    def enregistrer_paiement(vente, mode, montant=None, reference=""):
        montant = montant if montant is not None else vente.total
        if montant is None or montant <= 0:
            raise ValidationError("Le montant du paiement doit etre strictement positif.")
        statut = (
            Paiement.CONFIRME
            if mode == Paiement.ESPECES or (reference and reference.strip())
            else Paiement.EN_ATTENTE
        )
        return Paiement.objects.create(
            vente=vente,
            mode=mode,
            montant=montant,
            statut=statut,
            reference_transaction=reference or "",
        )
