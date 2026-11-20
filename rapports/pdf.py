from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from achats.models import CommandeAchat, ReceptionAchat
from stock.models import LotStock
from ventes.models import Vente


def _texte(valeur):
    return escape("" if valeur is None else str(valeur))


def _montant(valeur):
    try:
        valeur = Decimal(valeur)
    except Exception:
        valeur = Decimal("0")
    devise = settings.PHARMACIE.get("devise", "FCFA")
    return f"{valeur:,.2f} {devise}".replace(",", " ")


def _date(valeur):
    if not valeur:
        return "-"
    if hasattr(valeur, "tzinfo") and valeur.tzinfo is not None:
        valeur = timezone.localtime(valeur)
    return valeur.strftime("%d/%m/%Y")


def _date_heure(valeur):
    if not valeur:
        return "-"
    if hasattr(valeur, "tzinfo") and valeur.tzinfo is not None:
        valeur = timezone.localtime(valeur)
    return valeur.strftime("%d/%m/%Y a %H:%M")


class GenerateurPDF:
    """Generation des documents PDF de PharmaGest avec ReportLab."""

    infos_pharmacie = settings.PHARMACIE

    @staticmethod
    def _styles():
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="TitreDoc",
                parent=styles["Heading1"],
                fontSize=17,
                textColor=colors.HexColor("#0a5f61"),
                alignment=TA_RIGHT,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SousTitreDoc",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#5d6f7a"),
                alignment=TA_RIGHT,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Petit",
                parent=styles["Normal"],
                fontSize=8,
                leading=10,
            )
        )
        return styles

    @staticmethod
    def _entete(titre, sous_titre=""):
        styles = GenerateurPDF._styles()
        infos = settings.PHARMACIE
        gauche = Paragraph(
            f"<b>{_texte(infos.get('nom'))}</b><br/>"
            f"{_texte(infos.get('adresse'))}<br/>"
            f"Tel : {_texte(infos.get('telephone'))}<br/>"
            f"{_texte(infos.get('email'))}",
            styles["Petit"],
        )
        droite = Paragraph(
            f"{_texte(titre)}<br/><font size=8>{_texte(sous_titre)}</font>",
            styles["TitreDoc"],
        )
        tableau = Table([[gauche, droite]], colWidths=[100 * mm, 70 * mm])
        tableau.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#0f8b8d")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return tableau

    @staticmethod
    def _tableau(donnees, largeurs=None, alignements=None):
        tableau = Table(donnees, colWidths=largeurs, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f8b8d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfdbe2")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f9")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if alignements:
            for colonne, alignement in alignements.items():
                style.append(("ALIGN", (colonne, 1), (colonne, -1), alignement))
        tableau.setStyle(TableStyle(style))
        return tableau

    @staticmethod
    def _construire(titre, elements, sous_titre=""):
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            title=titre,
            author=settings.PHARMACIE.get("nom", "PharmaGest"),
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )
        styles = GenerateurPDF._styles()
        histoire = [GenerateurPDF._entete(titre, sous_titre), Spacer(1, 8 * mm)]
        histoire.extend(elements)
        histoire.append(Spacer(1, 6 * mm))
        histoire.append(
            Paragraph(
                "Document genere par PharmaGest - "
                f"{_date_heure(timezone.now())}",
                styles["SousTitreDoc"],
            )
        )
        document.build(histoire)
        return buffer.getvalue()

    @staticmethod
    def recu_vente(vente):
        styles = GenerateurPDF._styles()
        vente = Vente.objects.prefetch_related("lignes__medicament", "paiements").get(
            pk=vente.pk
        )
        elements = [
            Paragraph(
                f"Recu n <b>{_texte(vente.numero)}</b> - {_date_heure(vente.date_vente)}",
                styles["Normal"],
            ),
            Paragraph(
                f"Caissier : {_texte(vente.caissier.nom_complet())}"
                + (f" - Client : {_texte(vente.client)}" if vente.client else ""),
                styles["Petit"],
            ),
            Spacer(1, 4 * mm),
        ]
        donnees = [["#", "Medicament", "Lot", "Qte", "P.U.", "Total"]]
        for index, ligne in enumerate(vente.lignes.all(), start=1):
            donnees.append(
                [
                    str(index),
                    _texte(ligne.medicament),
                    _texte(ligne.lot.numero_lot),
                    str(ligne.quantite),
                    _montant(ligne.prix_unitaire_applique),
                    _montant(ligne.sous_total()),
                ]
            )
        elements.append(
            GenerateurPDF._tableau(
                donnees,
                largeurs=[8 * mm, 58 * mm, 26 * mm, 13 * mm, 28 * mm, 32 * mm],
                alignements={3: "RIGHT", 4: "RIGHT", 5: "RIGHT"},
            )
        )
        elements.append(Spacer(1, 4 * mm))
        elements.append(
            Paragraph(f"<b>Total a payer : {_montant(vente.total)}</b>", styles["Heading2"])
        )
        for paiement in vente.paiements.all():
            elements.append(
                Paragraph(
                    f"Paiement : {_texte(paiement.get_mode_display())} - "
                    f"{_montant(paiement.montant)} ({_texte(paiement.get_statut_display())})",
                    styles["Petit"],
                )
            )
        elements.append(Spacer(1, 5 * mm))
        elements.append(Paragraph("Merci de votre confiance.", styles["Normal"]))
        return GenerateurPDF._construire(
            "RECU DE VENTE", elements, f"N {vente.numero}"
        )

    @staticmethod
    def facture(vente):
        styles = GenerateurPDF._styles()
        vente = Vente.objects.prefetch_related("lignes__medicament", "paiements").get(
            pk=vente.pk
        )
        infos = settings.PHARMACIE
        elements = [
            Paragraph(f"Facture n <b>{_texte(vente.numero)}</b>", styles["Normal"]),
            Paragraph(
                f"Date : {_date_heure(vente.date_vente)} - Caissier : "
                f"{_texte(vente.caissier.nom_complet())}",
                styles["Petit"],
            ),
            Spacer(1, 4 * mm),
        ]
        if vente.client:
            elements.append(
                Paragraph(
                    "<b>Client</b><br/>"
                    f"{_texte(vente.client.nom)}<br/>"
                    f"{_texte(vente.client.telephone)}<br/>"
                    f"{_texte(vente.client.adresse)}",
                    styles["Petit"],
                )
            )
        else:
            elements.append(Paragraph("Client comptoir", styles["Petit"]))
        elements.append(Spacer(1, 4 * mm))
        donnees = [["#", "Designation", "Lot", "Qte", "P.U.", "Total"]]
        for index, ligne in enumerate(vente.lignes.all(), start=1):
            donnees.append(
                [
                    str(index),
                    _texte(ligne.medicament),
                    _texte(ligne.lot.numero_lot),
                    str(ligne.quantite),
                    _montant(ligne.prix_unitaire_applique),
                    _montant(ligne.sous_total()),
                ]
            )
        elements.append(
            GenerateurPDF._tableau(
                donnees,
                largeurs=[8 * mm, 58 * mm, 26 * mm, 13 * mm, 28 * mm, 32 * mm],
                alignements={3: "RIGHT", 4: "RIGHT", 5: "RIGHT"},
            )
        )
        elements.append(Spacer(1, 4 * mm))
        elements.append(
            Paragraph(f"<b>Montant total : {_montant(vente.total)}</b>", styles["Heading2"])
        )
        for paiement in vente.paiements.all():
            elements.append(
                Paragraph(
                    f"{_texte(paiement.get_mode_display())} : {_montant(paiement.montant)} "
                    f"- {_texte(paiement.get_statut_display())} "
                    f"{_texte(paiement.reference_transaction)}",
                    styles["Petit"],
                )
            )
        elements.append(Spacer(1, 4 * mm))
        elements.append(
            Paragraph(
                f"Statut de la vente : {_texte(vente.get_statut_display())}",
                styles["Petit"],
            )
        )
        elements.append(Paragraph(infos.get("nom", ""), styles["Petit"]))
        return GenerateurPDF._construire(
            "FACTURE", elements, f"N {vente.numero}"
        )

    @staticmethod
    def bon_commande(commande):
        styles = GenerateurPDF._styles()
        commande = CommandeAchat.objects.prefetch_related("lignes__medicament").get(
            pk=commande.pk
        )
        elements = [
            Paragraph(
                f"Bon de commande n <b>{_texte(commande.numero)}</b> - "
                f"{_date(commande.date_creation)}",
                styles["Normal"],
            ),
            Paragraph(
                f"Fournisseur : <b>{_texte(commande.fournisseur.nom)}</b><br/>"
                f"{_texte(commande.fournisseur.adresse)}<br/>"
                f"Tel : {_texte(commande.fournisseur.telephone)} - "
                f"{_texte(commande.fournisseur.email)}",
                styles["Petit"],
            ),
            Spacer(1, 4 * mm),
        ]
        donnees = [["#", "Medicament", "Qte commandee", "P.U. achat", "Sous-total"]]
        for index, ligne in enumerate(commande.lignes.all(), start=1):
            donnees.append(
                [
                    str(index),
                    _texte(ligne.medicament),
                    str(ligne.quantite_commandee),
                    _montant(ligne.prix_achat_unitaire),
                    _montant(ligne.sous_total()),
                ]
            )
        elements.append(
            GenerateurPDF._tableau(
                donnees,
                largeurs=[10 * mm, 78 * mm, 25 * mm, 28 * mm, 30 * mm],
                alignements={2: "RIGHT", 3: "RIGHT", 4: "RIGHT"},
            )
        )
        elements.append(Spacer(1, 4 * mm))
        elements.append(
            Paragraph(f"<b>Montant total : {_montant(commande.montant_total)}</b>", styles["Heading2"])
        )
        elements.append(
            Paragraph(f"Statut : {_texte(commande.get_statut_display())}", styles["Petit"])
        )
        return GenerateurPDF._construire(
            "BON DE COMMANDE", elements, f"N {commande.numero}"
        )

    @staticmethod
    def bon_reception(reception):
        styles = GenerateurPDF._styles()
        reception = ReceptionAchat.objects.prefetch_related(
            "lignes__ligne_achat__medicament", "lignes__lot"
        ).get(pk=reception.pk)
        elements = [
            Paragraph(
                f"Bon de reception n <b>{_texte(reception.numero_bon)}</b> - "
                f"{_date_heure(reception.date_reception)}",
                styles["Normal"],
            ),
            Paragraph(
                f"Commande : {_texte(reception.commande.numero)}<br/>"
                f"Fournisseur : <b>{_texte(reception.commande.fournisseur.nom)}</b><br/>"
                f"Recu par : {_texte(reception.recu_par or '-')}",
                styles["Petit"],
            ),
            Spacer(1, 4 * mm),
        ]
        donnees = [["#", "Medicament", "Lot", "Peremption", "Qte recue"]]
        for index, ligne in enumerate(reception.lignes.all(), start=1):
            donnees.append(
                [
                    str(index),
                    _texte(ligne.ligne_achat.medicament),
                    _texte(ligne.numero_lot),
                    _date(ligne.date_peremption),
                    str(ligne.quantite_recue),
                ]
            )
        elements.append(
            GenerateurPDF._tableau(
                donnees,
                largeurs=[10 * mm, 65 * mm, 30 * mm, 30 * mm, 25 * mm],
                alignements={4: "RIGHT"},
            )
        )
        elements.append(Spacer(1, 4 * mm))
        elements.append(
            Paragraph(
                f"<b>Montant receptionne : {_montant(reception.montant_total())}</b>",
                styles["Heading2"],
            )
        )
        elements.append(
            Paragraph(
                "Reception validee" if reception.est_validee else "Reception non validee",
                styles["Petit"],
            )
        )
        return GenerateurPDF._construire(
            "BON DE RECEPTION", elements, f"N {reception.numero_bon}"
        )

    @staticmethod
    def rapport_stock(lots=None):
        styles = GenerateurPDF._styles()
        if lots is None:
            lots = LotStock.objects.select_related("medicament").order_by(
                "medicament__nom_commercial", "date_peremption"
            )
        donnees = [["Medicament", "Lot", "Peremption", "Qte", "Valeur achat", "Etat"]]
        total = Decimal("0")
        for lot in lots:
            valeur = lot.quantite_disponible * lot.medicament.prix_achat
            total += valeur
            if lot.est_perime():
                etat = "Perime"
            elif lot.est_bloque:
                etat = "Bloque"
            else:
                etat = "Disponible"
            donnees.append(
                [
                    _texte(lot.medicament),
                    _texte(lot.numero_lot),
                    _date(lot.date_peremption),
                    str(lot.quantite_disponible),
                    _montant(valeur),
                    etat,
                ]
            )
        elements = [
            GenerateurPDF._tableau(
                donnees,
                largeurs=[48 * mm, 25 * mm, 24 * mm, 14 * mm, 30 * mm, 24 * mm],
                alignements={3: "RIGHT", 4: "RIGHT"},
            ),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Valeur totale du stock : {_montant(total)}</b>", styles["Heading2"]),
        ]
        return GenerateurPDF._construire(
            "RAPPORT DE STOCK", elements, f"{_date(timezone.now())}"
        )

    @staticmethod
    def rapport_ventes(ventes=None, debut=None, fin=None):
        styles = GenerateurPDF._styles()
        if ventes is None:
            ventes = Vente.objects.filter(statut=Vente.VALIDEE).select_related(
                "client", "caissier"
            )
        if debut:
            ventes = ventes.filter(date_vente__date__gte=debut)
        if fin:
            ventes = ventes.filter(date_vente__date__lte=fin)
        ventes = ventes.order_by("date_vente")
        donnees = [["Numero", "Date", "Client", "Caissier", "Total", "Statut"]]
        total = Decimal("0")
        for vente in ventes:
            if vente.statut == Vente.VALIDEE:
                total += vente.total
            donnees.append(
                [
                    _texte(vente.numero),
                    _date_heure(vente.date_vente),
                    _texte(vente.client or "Comptoir"),
                    _texte(vente.caissier.nom_complet()),
                    _montant(vente.total),
                    _texte(vente.get_statut_display()),
                ]
            )
        elements = [
            Paragraph(
                f"Periode : {_date(debut) if debut else 'debut'} - "
                f"{_date(fin) if fin else 'aujourd hui'}",
                styles["Petit"],
            ),
            Spacer(1, 3 * mm),
            GenerateurPDF._tableau(
                donnees,
                largeurs=[30 * mm, 30 * mm, 30 * mm, 30 * mm, 28 * mm, 22 * mm],
                alignements={4: "RIGHT"},
            ),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Chiffre d'affaires : {_montant(total)}</b>", styles["Heading2"]),
        ]
        return GenerateurPDF._construire(
            "RAPPORT DES VENTES", elements, f"{_date(timezone.now())}"
        )

    @staticmethod
    def rapport_achats(commandes=None, debut=None, fin=None):
        styles = GenerateurPDF._styles()
        if commandes is None:
            commandes = CommandeAchat.objects.select_related("fournisseur")
        if debut:
            commandes = commandes.filter(date_creation__date__gte=debut)
        if fin:
            commandes = commandes.filter(date_creation__date__lte=fin)
        commandes = commandes.order_by("date_creation")
        donnees = [["Numero", "Date", "Fournisseur", "Montant", "Statut"]]
        total = Decimal("0")
        for commande in commandes:
            if commande.statut != CommandeAchat.ANNULEE:
                total += commande.montant_total
            donnees.append(
                [
                    _texte(commande.numero),
                    _date(commande.date_creation),
                    _texte(commande.fournisseur.nom),
                    _montant(commande.montant_total),
                    _texte(commande.get_statut_display()),
                ]
            )
        elements = [
            Paragraph(
                f"Periode : {_date(debut) if debut else 'debut'} - "
                f"{_date(fin) if fin else 'aujourd hui'}",
                styles["Petit"],
            ),
            Spacer(1, 3 * mm),
            GenerateurPDF._tableau(
                donnees,
                largeurs=[32 * mm, 25 * mm, 52 * mm, 30 * mm, 26 * mm],
                alignements={3: "RIGHT"},
            ),
            Spacer(1, 4 * mm),
            Paragraph(f"<b>Total des achats : {_montant(total)}</b>", styles["Heading2"]),
        ]
        return GenerateurPDF._construire(
            "RAPPORT DES ACHATS", elements, f"{_date(timezone.now())}"
        )

    @staticmethod
    def liste_peremptions(lots=None):
        styles = GenerateurPDF._styles()
        if lots is None:
            lots = LotStock.objects.filter(quantite_disponible__gt=0).select_related(
                "medicament"
            )
        lots = lots.order_by("date_peremption")
        donnees = [["Medicament", "Lot", "Peremption", "Qte", "Jours restants", "Etat"]]
        for lot in lots:
            jours = lot.jours_avant_peremption()
            donnees.append(
                [
                    _texte(lot.medicament),
                    _texte(lot.numero_lot),
                    _date(lot.date_peremption),
                    str(lot.quantite_disponible),
                    str(jours),
                    "Perime" if jours < 0 else ("Proche" if jours <= 30 else "OK"),
                ]
            )
        elements = [
            GenerateurPDF._tableau(
                donnees,
                largeurs=[50 * mm, 28 * mm, 26 * mm, 14 * mm, 24 * mm, 22 * mm],
                alignements={3: "RIGHT", 4: "CENTER"},
            )
        ]
        return GenerateurPDF._construire(
            "LISTE DES PEREMPTIONS", elements, f"{_date(timezone.now())}"
        )
