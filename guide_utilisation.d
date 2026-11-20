================================================================================
                   PHARMA GEST - GUIDE D'UTILISATION DU PROJET
          Application de gestion de pharmacie (Python / Django - MVT)
================================================================================

Version : 1.0
Date    : 2026-11-18
Projet  : gestion_pharmacie

================================================================================
SOMMAIRE
================================================================================
1. Présentation du projet
2. Architecture technique (MVT / Django)
3. Diagramme de classes - référence
4. Modules fonctionnels détaillés
   4.1 Utilisateurs, rôles et journal d'audit (Module A)
   4.2 Catalogue des médicaments et stock (Modules B, C, G)
   4.3 Fournisseurs et achats (Modules D, F)
   4.4 Clients, ventes et retours (Modules E, H, I)
   4.5 Services métier, tableaux de bord et rapports PDF (Modules J, K)
5. Règles de gestion (RG)
6. Installation et mise en route
7. Utilisation par rôle
8. Maintenance et sécurité
9. Référence croisée avec le diagramme de classes

================================================================================
1. PRÉSENTATION DU PROJET
================================================================================

PharmaGest est une application web de gestion de pharmacie développée avec
Python et le framework Django (architecture MVT : Modèle - Vue - Template).

Elle permet de gérer :
- Le catalogue des médicaments (catégories, lots, péremption FEFO)
- Le stock (mouvements traçables, inventaire physique, alertes)
- Les achats (fournisseurs, commandes, réceptions)
- Les ventes (clients, caissiers, paiements, retours)
- Les rapports et documents PDF (reçus, factures, bons de commande/réception)
- Les utilisateurs, rôles, permissions et journal d'audit

Le diagramme de classes du projet est fourni dans le fichier :
  pharmagest-diagrammes-classes.html

Ce guide s'y réfère systématiquement pour décrire chaque entité, ses
attributs, ses méthodes et ses relations (cardinalités, composition,
agrégation, héritage, dépendance).

================================================================================
2. ARCHITECTURE TECHNIQUE (MVT / DJANGO)
================================================================================

PharmaGest suit l'architecture MVT de Django :

- Modèle (models.py) : définit la structure des données et la logique
  métier (contraintes, méthodes de calcul, validation).
- Vue (views.py) : gère les requêtes HTTP, appelle les services et rend
  les templates.
- Template (templates/*.html) : affiche l'interface utilisateur (Base
  HTML dans templates/base.html, Bootstrap 5).

Applications Django du projet :

+----------------+--------------------------------------------------+
| Application    | Rôle                                             |
+----------------+--------------------------------------------------+
| utilisateurs   | Authentification, rôles, permissions, journal    |
| medicaments    | Catalogue : catégories et médicaments            |
| stock          | Lots, mouvements de stock, inventaire physique   |
| fournisseurs   | Fournisseurs et historique d'achats              |
| achats         | Commandes d'achat, lignes, réceptions            |
| clients        | Clients et historique des ventes                 |
| ventes         | Ventes, lignes de vente, paiements, retours      |
| rapports       | Génération de documents PDF (ReportLab)          |
+----------------+--------------------------------------------------+

Fichier de gestion : manage.py
Base de données par défaut : db.sqlite3 (développement)

================================================================================
3. DIAGRAMME DE CLASSES - RÉFÉRENCE
================================================================================

Le fichier pharmagest-diagrammes-classes.html contient le diagramme de
classes complet du projet. Il est organisé en 5 sections :

1. Utilisateurs, rôles et journal d'audit
2. Catalogue des médicaments et gestion du stock
3. Fournisseurs, commandes d'achat et réceptions
4. Clients, ventes, paiements et retours
5. Services métier, tableau de bord et rapports PDF

Légende du diagramme (selon pharmagest-diagrammes-classes.html) :
  +  Attribut / méthode public (visibilité publique)
  -  Attribut / méthode privé (visibilité privée)
  🔑 Clé primaire
  Association simple (1 — 0..*, 1 — 1..*, etc.)
  Composition (losange plein) : fort couplage, cycle de vie lié
  Agrégation (losange vide) : lien plus faible
  Héritage (triangle vide)
  Dépendance (pointillés + flèche) : « utilise »

Types de classe indiqués dans le diagramme :
  - Classe issue du cahier des charges (bordure normale)
  - Classe ajoutée pour compléter la conception (bordure orange)
  - Classe de service / logique métier (bordure décassée bleue)
  - Classe de référence (décrite ailleurs, bordure grise)

================================================================================
4. MODULES FONCTIONNELS DÉTAILLÉS
================================================================================

------------------------------------------------------------
4.1 UTILISATEURS, RÔLES ET JOURNAL D'AUDIT (Module A)
------------------------------------------------------------

Référence diagramme : section « 1. Utilisateurs, rôles et journal d'audit »

Classes impliquées :
  - Role (utilisateurs.Role)
  - Utilisateur (utilisateurs.Utilisateur, étend AbstractUser)
  - JournalAudit (utilisateurs.JournalAudit)

Relations (cardinalités) :
  - Role 1 — 0..* Utilisateur : un rôle peut être affecté à plusieurs
    utilisateurs ; un utilisateur a un rôle (ou aucun).
  - Utilisateur 1 — 0..* JournalAudit : un utilisateur produit plusieurs
    entrées de journal d'audit.

Attributs clés :
  Role : id, nom (unique), description, permissions (ManyToMany vers
    Permission Django)
  Utilisateur : id, username (unique), password (haché), first_name,
    last_name, email, telephone, role (ForeignKey Role), is_active,
    date_creation, derniere_connexion
  JournalAudit : id, utilisateur (FK), action (CREATION, MODIFICATION,
    SUPPRESSION, VALIDATION, ANNULATION, CONNEXION, DECONNEXION,
    RECEPTION, PAIEMENT, RETOUR, INVENTAIRE, ACCES_REFUSE…),
    modele_cible, objet_id, details (JSON), adresse_ip, date_action

Méthodes importantes :
  Role.a_permission(code) : vérifie une permission « app_label.codename »
  Utilisateur.peut(action) : contrôle d'accès centralisé (vues/templates)
  Utilisateur.activer() / desactiver() / changer_mot_de_passe()
  JournalAudit.enregistrer(user, action, objet, details, request)

Règles :
  - Le mot de passe est haché par Django (PBKDF2), jamais stocké en clair.
  - Le journal d'audit est en ajout seulement (pas de modification ni
    suppression).
  - L'administrateur peut affecter plusieurs permissions via Role.

------------------------------------------------------------
4.2 CATALOGUE DES MÉDICAMENTS ET STOCK (Modules B, C, G)
------------------------------------------------------------

Référence diagramme : section « 2. Catalogue des médicaments et
gestion du stock »

Classes impliquées :
  - Categorie (medicaments.Categorie)
  - Medicament (medicaments.Medicament)
  - LotStock (stock.LotStock)
  - MouvementStock (stock.MouvementStock)
  - Inventaire (stock.Inventaire) [ajouté]
  - LigneInventaire (stock.LigneInventaire) [ajouté]

Relations (cardinalités) :
  - Categorie 1 — 0..* Medicament : une catégorie classe plusieurs
    médicaments ; suppression interdite si utilisée (PROTECT).
  - Medicament 1 — 0..* LotStock : un médicament a des lots (composition).
  - LotStock 1 — 0..* MouvementStock : chaque variation de stock est
    historisée (RG09).
  - Inventaire 1 — 1..* LigneInventaire : un inventaire contient au moins
    une ligne (composition).
  - LigneInventaire 1 — 1 LotStock : une ligne concerne un lot.

Attributs clés :
  Categorie : id, nom (unique), description
  Medicament : id, nom_commercial, denomination_generique, categorie
    (FK PROTECT), forme (comprimé/sirop/gélule/injection/pommade/
    gouttes/autre), dosage, laboratoire, code_barres (unique, null),
    photo (ImageField, max 2 Mo, JPEG/PNG/WebP), prix_achat (>0),
    prix_vente (>0), seuil_alerte, statut (ACTIF/ARCHIVE),
    date_creation
  LotStock : id, medicament (FK), numero_lot, date_peremption,
    quantite_recue, quantite_disponible (>=0), est_bloque, motif_blocage,
    date_reception
  MouvementStock : id, lot (FK), type (ENTREE_ACHAT, SORTIE_VENTE,
    RETOUR, CORRECTION, INVENTAIRE, PEREMPTION), quantite (signée),
    stock_apres, reference_type, reference_id, motif, utilisateur (FK),
    date_mouvement. En ajout/suppression interdits.
  Inventaire : id, date_inventaire, statut (EN_COURS/VALIDE/ANNULE),
    realise_par (FK Utilisateur), commentaire
  LigneInventaire : id, inventaire (FK), lot (FK), quantite_theorique,
    quantite_comptee

Méthodes importantes :
  Medicament.stock_total() : somme des quantités disponibles des lots
    délivrables
  Medicament.est_en_alerte() / est_en_rupture()
  Medicament.archiver() / desarchiver() / peut_etre_supprime()
  LotStock.est_perime() / est_delivrable() / jours_avant_peremption()
  LotStock.bloquer(motif) / debloquer()
  LotStock.lots_fefo(medicament) : lots triés par péremption la plus proche
  MouvementStock.enregistrer(...) : crée un mouvement en ajout seulement
  Inventaire.valider(utilisateur) : applique les écarts et crée des
    mouvements INVENTAIRE (transaction atomique)
  Inventaire.annuler()
  LigneInventaire.ecart() : quantite_comptee - quantite_theorique

Règles (RG) :
  - RG02 : code_barres unique lorsqu'il est renseigné.
  - RG07 : quantite_disponible ne peut jamais être négative (CheckConstraint).
  - RG08 / FEFO : les lots périmés ou bloqués sont exclus de la vente ;
    les lots à péremption la plus proche sortent en premier.
  - Un médicament lié à des opérations est archivé (statut ARCHIVE),
    jamais supprimé.

------------------------------------------------------------
4.3 FOURNISSEURS ET ACHATS (Modules D, F)
------------------------------------------------------------

Référence diagramme : section « 3. Fournisseurs, commandes d'achat et
réceptions »

Classes impliquées :
  - Fournisseur (fournisseurs.Fournisseur)
  - CommandeAchat (achats.CommandeAchat)
  - LigneAchat (achats.LigneAchat)
  - ReceptionAchat (achats.ReceptionAchat)
  - LigneReception (achats.LigneReception) [ajouté]

Relations (cardinalités) :
  - Fournisseur 1 — 0..* CommandeAchat : un fournisseur reçoit plusieurs
    commandes ; un fournisseur désactivé conserve son historique.
  - CommandeAchat 1 — 1..* LigneAchat : une commande contient au moins une
    ligne (composition).
  - CommandeAchat 1 — 0..* ReceptionAchat : réception partielle possible
    (statut PARTIELLE).
  - ReceptionAchat 1 — 1..* LigneReception : chaque réception détaille des
    lignes (composition).
  - LigneAchat * — 1 Medicament : le prix d'achat est figé sur la ligne (RG12).

Attributs clés :
  Fournisseur : id, nom, adresse, telephone, email, numero_fiscal,
    contact_principal, est_actif, date_creation
  CommandeAchat : id, numero (unique, « CA-… »), fournisseur (FK),
    statut (BROUILLON/COMMANDEE/PARTIELLE/COMPLETE/ANNULEE),
    date_creation, date_commande, montant_total, cree_par (FK Utilisateur)
  LigneAchat : id, commande (FK), medicament (FK), quantite_commandee
    (>0), quantite_recue, prix_achat_unitaire (>0)
  ReceptionAchat : id, numero_bon (unique, « BR-… »), commande (FK),
    date_reception, recu_par (FK Utilisateur), est_validee
  LigneReception : id, reception (FK), ligne_achat (FK), numero_lot,
    date_peremption, quantite_recue (>0), lot (FK LotStock, null)

Méthodes importantes :
  CommandeAchat.calculer_total() / recalculer_total()
  CommandeAchat.valider() : passe en COMMANDEE, nécessite au moins une ligne
  CommandeAchat.annuler() : impossible si déjà réceptionnée validée
  CommandeAchat.mettre_a_jour_statut()
  LigneAchat.sous_total() / reste_a_recevoir()
  ReceptionAchat.valider(utilisateur) : entre le stock via ServiceStock
    (transaction atomique), crée les Lots et mouvements ENTREE_ACHAT
  LigneReception.creer_lot() : crée ou met à jour un LotStock

Règles (RG) :
  - RG04 : une commande ne modifie pas le stock.
  - RG05 : seule la réception validée augmente le stock, une seule fois.
  - RG12 : le prix d'achat est figé sur la ligne.

------------------------------------------------------------
4.4 CLIENTS, VENTES ET RETOURS (Modules E, H, I)
------------------------------------------------------------

Référence diagramme : section « 4. Clients, ventes, paiements et retours »

Classes impliquées :
  - Client (clients.Client)
  - Vente (ventes.Vente)
  - LigneVente (ventes.LigneVente)
  - Paiement (ventes.Paiement)
  - RetourVente (ventes.RetourVente)

Relations (cardinalités) :
  - Client 0..1 — 0..* Vente : une vente peut être sans client (comptoir).
  - Vente 1 — 1..* LigneVente : une vente contient au moins une ligne
    (composition).
  - LigneVente * — 1 LotStock : lot ni périmé ni bloqué ; quantité <= stock
    du lot (RG07/RG08).
  - Vente 1 — 1..* Paiement : une vente est réglée par un ou plusieurs
    paiements.
  - LigneVente 1 — 0..* RetourVente : opération compensatoire + mouvement
    RETOUR, pas de suppression.

Attributs clés :
  Client : id, nom, telephone, adresse, est_actif, date_creation
  Vente : id, numero (unique, « V-… »), client (FK null), caissier (FK),
    date_vente, statut (EN_COURS/VALIDEE/ANNULEE), total,
    cle_idempotence (UUID unique), motif_annulation
  LigneVente : id, vente (FK), medicament (FK), lot (FK), quantite (>0),
    prix_unitaire_applique (>0)
  Paiement : id, vente (FK), mode (ESPECES/MOBILE_MONEY/AUTRE), montant,
    statut (EN_ATTENTE/CONFIRME/ECHOUE/REMBOURSE),
    reference_transaction, date_paiement
  RetourVente : id, vente (FK), ligne_vente (FK), quantite_retournee (>0),
    motif, remis_en_stock, montant_rembourse, utilisateur (FK), date_retour,
    est_valide

Méthodes importantes :
  Vente.ajouter_ligne(lot, quantite, prix_unitaire)
  Vente.calculer_total() / recalculer_total()
  Vente.valider(utilisateur) : vente atomique via ServiceVente
    (@transaction.atomic)
  Vente.annuler(motif, utilisateur)
  LigneVente.sous_total() / verifier_disponibilite()
  LigneVente.quantite_retournee() / quantite_restante_retournable()
  Paiement.confirmer() / rembourser(montant)
  RetourVente.est_eligible_remise_en_stock() / valider(utilisateur)

Règles de vente :
  - Quantité nulle ou négative refusée ; quantité > stock refusée.
  - cle_idempotence empêche la validation en double d'une même vente (RG06).
  - La validation de la vente et la sortie de stock s'exécutent dans une
    même transaction atomique.

------------------------------------------------------------
4.5 SERVICES MÉTIER, TABLEAUX DE BORD ET RAPPORTS PDF (Modules J, K)
------------------------------------------------------------

Référence diagramme : section « 5. Services métier, tableau de bord et
rapports PDF »

Classes de service (aucune attribut persistant) :
  - ServiceStock : entrer_stock(reception), sortir_stock_fefo(medicament,
    qte), corriger(lot, qte, motif), alertes_stock_faible(),
    lots_proches_peremption(jours), lots_perimes()
  - ServiceVente : valider_vente(vente) (atomique), traiter_retour(retour),
    annuler_vente(vente, motif)
  - ServiceStatistiques : medicaments_actifs(), ventes_du_jour(),
    ventes_periode(debut, fin), achats_periode(debut, fin),
    produits_plus_vendus(n), chiffre_affaires(), encaissements(),
    marge_commerciale()
  - GenerateurPDF (ReportLab) : recu_vente(vente), facture(vente),
    bon_commande(commande), bon_reception(reception), rapport_stock(),
    rapport_ventes(debut, fin), rapport_achats(debut, fin),
    liste_peremptions(jours)

Dépendances :
  - ServiceStock utilise LotStock et MouvementStock (référence)
  - ServiceStatistiques lit Vente, CommandeAchat, Medicament (référence)
  - GenerateurPDF génère des documents PDF avec numéro, date, lignes,
    prix appliqués, total et informations de la pharmacie

Règles importantes :
  - Le chiffre d'affaires, les encaissements et la marge commerciale sont
    trois indicateurs distincts ; la marge n'est pas un bénéfice net.
  - Les valeurs du tableau de bord sont calculées depuis la base, jamais
    saisies manuellement.

================================================================================
5. RÈGLES DE GESTION (RG)
================================================================================

RG02 : code_barres unique lorsqu'il est renseigné (Medicament).
RG04 : une commande d'achat ne modifie pas le stock.
RG05 : seule la réception validée augmente le stock, une seule fois.
RG06 : cle_idempotence empêche la validation en double d'une vente.
RG07 : quantite_disponible ne peut jamais être négative (CheckConstraint).
RG08 / FEFO : lots périmés ou bloqués exclus de la vente ; sortie par
      péremption la plus proche en premier.
RG09 : toute variation de stock est tracée par un MouvementStock.
RG11 : contrôle d'accès par rôles et permissions (Utilisateur.peut / Role).
RG12 : le prix (achat ou vente) est figé sur la ligne correspondante.

================================================================================
6. INSTALLATION ET MISE EN ROUTE
================================================================================

Prérequis :
  - Python 3.10+
  - pip / virtualenv

Étapes :

1. Cloner / ouvrir le projet :
   cd D:\S5\Django\gestion_pharmacie

2. Créer et activer l'environnement virtuel :
   python -m venv venv
   venv\Scripts\activate

3. Installer les dépendances :
   pip install -r requirements.txt
   (si le fichier existe, sinon installer django, pillow, reportlab)

4. Appliquer les migrations :
   python manage.py migrate

5. Créer un super-utilisateur :
   python manage.py createsuperuser

6. Lancer le serveur de développement :
   python manage.py runserver

7. Accéder à l'application :
   http://127.0.0.1:8000/
   Administration Django : http://127.0.0.1:8000/admin/

Données de test recommandées :
  - Créer au moins un Role (Administrateur, Pharmacien, Gestionnaire de
    stock, Caissier, Responsable de gestion)
  - Créer des Utilisateurs liés à ces rôles
  - Créer des Categories, puis des Medicaments
  - Créer des Fournisseurs, des CommandesAchat, puis valider des
    RéceptionsAchat pour alimenter le stock (Lots)
  - Effectuer des Ventes avec Paiements et éventuels Retours

================================================================================
7. UTILISATION PAR RÔLE
================================================================================

+------------------+-----------------------------------------------------+
| Rôle             | Permissions typiques                                |
+------------------+-----------------------------------------------------+
| Administrateur   | Gestion des utilisateurs, rôles, journal d'audit,   |
|                  | configuration pharmacie, tous les modules           |
| Pharmacien       | Catalogue médicaments, stock, alertes, inventaire   |
| Gestionnaire de  | Achats, réceptions, fournisseurs, rapports stock    |
| stock            |                                                     |
| Caissier         | Ventes, paiements, retours, reçus PDF               |
| Responsable de   | Tableaux de bord, statistiques, rapports PDF ventes |
| gestion          | et achats                                           |
+------------------+-----------------------------------------------------+

Contrôle d'accès :
  - Utiliser Utilisateur.peut('app_label.codename') dans les vues.
  - Le badge de rôle s'affiche dans la topbar (base.html).
  - Le journal d'audit trace automatiquement les actions importantes.

================================================================================
8. MAINTENANCE ET SÉCURITÉ
================================================================================

- Mots de passe : hachés par Django (PBKDF2), jamais en clair.
- Journal d'audit : ajout seulement, suppression et modification interdites.
- Mouvements de stock : ajout seulement, ni modifiable ni supprimable.
- Médicaments liés à des opérations : archivés (statut ARCHIVE), non
  supprimés.
- Images de médicaments : max 2 Mo, formats JPEG/PNG/WebP uniquement.
- Sauvegarder régulièrement le fichier db.sqlite3 et le dossier des
  médias (photos).
- Les documents PDF générés (ReportLab) portent les informations de la
  pharmacie, numéro, date, lignes, prix et total.

================================================================================
9. RÉFÉRENCE CROISÉE AVEC LE DIAGRAMME DE CLASSES
================================================================================

Le tableau ci-dessous fait le lien entre ce guide, les classes du diagramme
(pharmagest-diagrammes-classes.html) et les fichiers modèles Django.

+----------------------+-------------------------------+----------------------+
| Guide (section)      | Classe (diagramme)            | Fichier modèle       |
+----------------------+-------------------------------+----------------------+
| 4.1 Utilisateurs     | Role                          | utilisateurs/models.py
|                      | Utilisateur (AbstractUser)    | utilisateurs/models.py
|                      | JournalAudit                  | utilisateurs/models.py
| 4.2 Catalogue /      | Categorie                     | medicaments/models.py
| Stock                | Medicament                    | medicaments/models.py
|                      | LotStock                      | stock/models.py
|                      | MouvementStock                | stock/models.py
|                      | Inventaire (ajouté)           | stock/models.py
|                      | LigneInventaire (ajouté)      | stock/models.py
| 4.3 Achats           | Fournisseur                   | fournisseurs/models.py
|                      | CommandeAchat                 | achats/models.py
|                      | LigneAchat                    | achats/models.py
|                      | ReceptionAchat                | achats/models.py
|                      | LigneReception (ajouté)       | achats/models.py
| 4.4 Ventes           | Client                        | clients/models.py
|                      | Vente                         | ventes/models.py
|                      | LigneVente                    | ventes/models.py
|                      | Paiement                      | ventes/models.py
|                      | RetourVente                   | ventes/models.py
| 4.5 Services         | ServiceStock (service)        | stock/services.py (à créer)
|                      | ServiceVente (service)        | ventes/services.py
|                      | ServiceStatistiques (service) | rapports/services.py (à créer)
|                      | GenerateurPDF (service)       | rapports/services.py (à créer)
+----------------------+-------------------------------+----------------------+

Fichiers associés :
  - Diagramme de classes : pharmagest-diagrammes-classes.html
  - MCD (Modèle Conceptuel de Données) : PharmaGest_MCD.pdf
  - Templates : templates/ (base.html, includes/navigation.html, etc.)
  - Base de données : db.sqlite3

================================================================================
FIN DU GUIDE D'UTILISATION - PHARMA GEST
================================================================================
