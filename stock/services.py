from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce

from medicaments.models import Medicament

from .models import LotStock, MouvementStock


class ServiceStock:
    """Logique metier sensible du stock : entrees, sorties FEFO, corrections."""

    @staticmethod
    @transaction.atomic
    def entrer_stock(reception, utilisateur=None):
        """Valide une reception : cree les lots et augmente le stock une seule fois."""
        from achats.models import LigneAchat, ReceptionAchat

        rec = ReceptionAchat.objects.select_for_update().get(pk=reception.pk)
        if rec.est_validee:
            raise ValidationError("Cette reception a deja ete validee.")
        commande = rec.commande
        if commande.statut not in {
            commande.COMMANDEE,
            commande.PARTIELLE,
        }:
            raise ValidationError(
                "Seule une commande validee et non soldee peut etre receptionnee."
            )

        lignes = list(rec.lignes.select_related("ligne_achat__medicament"))
        if not lignes:
            raise ValidationError("Une reception doit contenir au moins une ligne.")

        for ligne_reception in lignes:
            ligne_achat = LigneAchat.objects.select_for_update().get(
                pk=ligne_reception.ligne_achat_id
            )
            quantite = ligne_reception.quantite_recue
            if quantite is None or quantite <= 0:
                raise ValidationError("Les quantites receptionnees doivent etre strictement positives.")
            if quantite > ligne_achat.reste_a_recevoir():
                raise ValidationError(
                    f"La quantite recue depasse le reste a recevoir pour {ligne_achat.medicament}."
                )
            if ligne_reception.date_peremption < date.today():
                raise ValidationError(
                    f"Le lot {ligne_reception.numero_lot} est deja perime : reception refusee."
                )

            lot = ligne_reception.creer_lot()
            ligne_achat.quantite_recue += quantite
            ligne_achat.save(update_fields=["quantite_recue"])

            MouvementStock.enregistrer(
                lot,
                MouvementStock.ENTREE_ACHAT,
                quantite,
                utilisateur=utilisateur or rec.recu_par,
                reference_type="ReceptionAchat",
                reference_id=rec.pk,
                motif=f"Reception du bon {rec.numero_bon}",
            )

        rec.est_validee = True
        rec.save(update_fields=["est_validee"])
        commande.mettre_a_jour_statut()
        return rec

    @staticmethod
    @transaction.atomic
    def sortir_stock_fefo(
        medicament,
        quantite,
        utilisateur=None,
        reference_type="",
        reference_id=None,
        motif="",
    ):
        """Sort la quantite demandee en respectant l'ordre FEFO."""
        quantite = int(quantite)
        if quantite <= 0:
            raise ValidationError("La quantite a sortir doit etre strictement positive.")

        lots = list(LotStock.lots_fefo(medicament, for_update=True))
        disponible = sum(lot.quantite_disponible for lot in lots)
        if disponible < quantite:
            raise ValidationError(
                f"Stock insuffisant pour {medicament} : disponible {disponible}, demande {quantite}."
            )

        restant = quantite
        sorties = []
        for lot in lots:
            if restant <= 0:
                break
            prise = min(lot.quantite_disponible, restant)
            lot.quantite_disponible -= prise
            lot.save(update_fields=["quantite_disponible"])
            MouvementStock.enregistrer(
                lot,
                MouvementStock.SORTIE_VENTE,
                -prise,
                utilisateur=utilisateur,
                reference_type=reference_type,
                reference_id=reference_id,
                motif=motif,
            )
            sorties.append({"lot": lot, "quantite": prise})
            restant -= prise
        return sorties

    @staticmethod
    @transaction.atomic
    def corriger(lot, delta, motif, utilisateur=None):
        """Applique une correction signee a un lot et trace le mouvement."""
        delta = int(delta)
        if delta == 0:
            raise ValidationError("La correction doit modifier la quantite.")
        lot = LotStock.objects.select_for_update().get(pk=lot.pk)
        nouvelle_quantite = lot.quantite_disponible + delta
        if nouvelle_quantite < 0:
            raise ValidationError("La correction rendrait la quantite du lot negative.")
        lot.quantite_disponible = nouvelle_quantite
        lot.save(update_fields=["quantite_disponible"])
        MouvementStock.enregistrer(
            lot,
            MouvementStock.CORRECTION,
            delta,
            utilisateur=utilisateur,
            reference_type="Correction",
            reference_id=lot.pk,
            motif=motif,
        )
        return lot

    @staticmethod
    def alertes_stock_faible():
        aujourdhui = date.today()
        return (
            Medicament.objects.filter(statut=Medicament.ACTIF)
            .annotate(
                stock_disponible=Coalesce(
                    Sum(
                        "lots__quantite_disponible",
                        filter=Q(
                            lots__est_bloque=False,
                            lots__date_peremption__gte=aujourdhui,
                        ),
                    ),
                    0,
                )
            )
            .filter(stock_disponible__lte=F("seuil_alerte"))
            .order_by("stock_disponible", "nom_commercial")
        )

    @staticmethod
    def lots_proches_peremption(jours=30):
        aujourdhui = date.today()
        return (
            LotStock.objects.filter(
                quantite_disponible__gt=0,
                est_bloque=False,
                date_peremption__gte=aujourdhui,
                date_peremption__lte=aujourdhui + timedelta(days=int(jours)),
            )
            .select_related("medicament")
            .order_by("date_peremption")
        )

    @staticmethod
    def lots_perimes():
        return (
            LotStock.objects.filter(
                quantite_disponible__gt=0, date_peremption__lt=date.today()
            )
            .select_related("medicament")
            .order_by("date_peremption")
        )

    @staticmethod
    def valeur_stock():
        total = 0
        for lot in LotStock.objects.filter(
            quantite_disponible__gt=0, date_peremption__gte=date.today()
        ).select_related("medicament"):
            total += lot.quantite_disponible * lot.medicament.prix_achat
        return total
