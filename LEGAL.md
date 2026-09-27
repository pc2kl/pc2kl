# Legal notice / Mentions légales

*English version first, French version below. In case of discrepancy regarding the
application of French law, the French version prevails.*

---

## English

### 1. Independence and trademarks

This project is an independent work of its author, acting in a personal capacity.
It is **not affiliated with, sponsored, endorsed, reviewed, or supported by FANUC
Corporation, FANUC America Corporation, or any of their affiliates**, nor by the
author's employer or any other company.

"FANUC", "KAREL", "ROBOGUIDE", "WinOLPC" and any other product names are trademarks of
their respective owners. They are used only in a descriptive manner, to indicate the
file format the tool is compatible with, as permitted by trademark law (referential /
nominative use). No logo, trade dress or official material is used.

### 2. Purpose

`pc2kl` is an interoperability and maintenance tool. Its sole purpose is to let the
lawful owner of a KAREL program, or a person authorised by that owner, recover a
readable source file when the original source has been lost, in order to maintain the
program, correct it, or port it to a newer controller.

It is **not** designed or intended to obtain, copy, or redistribute third-party
programs, trade secrets or know-how, to circumvent any technical protection measure,
licence check or access control, or to modify, analyse or reproduce FANUC software.

### 3. Content of this repository

This repository contains only original code and data written by the author:

* **No FANUC software** (executables, libraries, drivers, support or configuration
  files, firmware) and no part of such software.
* **No FANUC documentation** or excerpt thereof. Test programs refer to built-in names
  and syntax only as needed to exercise the language, as any KAREL program does.
* **No third-party program** and no `.pc` file compiled from a third-party program.
* **No personal data.**

### 4. How the format information was obtained

The information on the `.pc` file format and the data tables shipped with the tool
were obtained by **observing, studying and testing the behaviour of a lawfully
licensed translator as a black box**: test programs written by the author, based on
the KAREL reference manual, were compiled on the author's licensed
workstation during its normal use, and the resulting output files were compared with
their sources. The data tables published here were derived exclusively from these
observations, and no part of the translator is reproduced.

The full test corpus, scripts, and derivation reports needed to reproduce this work
are provided in the `tests/` folder, so that anyone can verify how every table entry
was established.

The functionality of a program, a programming language, and the format of data files
are ideas and principles that are not, as such, protected by copyright (see, in EU
law, Directive 2009/24/EC, recital 11 and Art. 5(3); CJEU, 2 May 2012, *SAS Institute*,
C-406/10). The right of a lawful user to observe, study or test the functioning of a
program in order to determine the ideas and principles underlying it cannot be
excluded by contract (Directive 2009/24/EC, Art. 5(3) and 8; French Intellectual
Property Code, Art. L.122-6-1 III and V).

### 5. User responsibility

By using this software, you agree that:

* you will use it **only on programs you own or are authorised to maintain**, and you
  are solely responsible for verifying that authorisation;
* you will comply with any licence agreement binding you, and with the laws applicable
  to you, which may differ from French or EU law;
* you will not use it to infringe intellectual property rights, trade secrets, or
  contractual obligations of any person;
* recovered code is **not guaranteed to be correct**. You must review it and validate
  it on a simulator before any use on real equipment. **Industrial robots can cause
  death, serious injury and damage**; all applicable safety standards and procedures
  (e.g. ISO 10218, risk assessment, qualified personnel) remain your responsibility.

### 6. No warranty — limitation of liability

The software is provided **"as is", without warranty of any kind**, express or implied,
including but not limited to merchantability, fitness for a particular purpose,
accuracy, and non-infringement. To the maximum extent permitted by applicable law, the
author shall not be liable for any direct or indirect damage, loss of production, loss
of data, injury, or claim of any kind arising from the use of, or inability to use,
this software or its output. Where the law does not allow such exclusion, liability is
limited to the minimum permitted.

### 7. Rights holders

If you are a rights holder and believe that anything in this repository infringes your
rights, please open an issue or contact the author, identifying the content concerned
and the right invoked. Any reasonable request will be examined promptly and in good
faith, and the content will be removed or modified if justified.

---

## Français

### 1. Indépendance et marques

Ce projet est une œuvre indépendante de son auteur, réalisée à titre personnel. Il
**n'est ni affilié, ni parrainé, ni approuvé, ni vérifié, ni soutenu par FANUC
Corporation, FANUC America Corporation ou l'une de leurs filiales**, ni par l'employeur
de l'auteur ou toute autre société.

« FANUC », « KAREL », « ROBOGUIDE », « WinOLPC » et tout autre nom de produit sont des
marques de leurs titulaires respectifs. Ils sont cités uniquement pour indiquer le
format de fichier avec lequel l'outil est compatible (usage descriptif et référentiel,
art. L.713-6 du Code de la propriété intellectuelle et art. 14 du règlement (UE)
2017/1001). Aucun logo ni élément officiel n'est utilisé.

### 2. Objet

`pc2kl` est un outil d'interopérabilité et de maintenance. Son seul objet est de
permettre au titulaire légitime d'un programme KAREL, ou à une personne autorisée par
lui, de retrouver un source lisible lorsque le source d'origine a été perdu, afin de
maintenir ce programme, de le corriger ou de le porter sur un contrôleur plus récent.

Il n'est **ni conçu ni destiné** à obtenir, copier ou diffuser des programmes de tiers,
des secrets d'affaires ou un savoir-faire, à contourner une mesure technique de
protection, un contrôle de licence ou d'accès, ni à modifier, analyser ou reproduire
un logiciel FANUC.

### 3. Contenu du dépôt

Ce dépôt ne contient que du code et des données originaux écrits par l'auteur :

* **aucun logiciel FANUC** (exécutable, bibliothèque, pilote, fichier de support ou de
  configuration, micrologiciel), ni aucune partie d'un tel logiciel ;
* **aucune documentation FANUC** ni extrait de documentation ; les programmes de test
  n'utilisent les noms et la syntaxe du langage que dans la mesure nécessaire pour
  l'exercer, comme tout programme KAREL ;
* **aucun programme de tiers** et aucun `.pc` compilé à partir d'un programme de tiers ;
* **aucune donnée personnelle**.

### 4. Origine des informations sur le format

Les informations sur le format `.pc` et les tables fournies avec l'outil ont été
obtenues en **observant, étudiant et testant le fonctionnement d'un traducteur utilisé
sous licence, comme une boîte noire** : des programmes de test écrits par l'auteur à
partir du manuel de référence KAREL ont été compilés sur le
poste de l'auteur, dans le cadre de son utilisation normale, et les fichiers produits
ont été comparés à leurs sources. Les tables publiées ici ont été établies
exclusivement à partir de ces observations, et aucune partie du traducteur n'est
reproduite.

L'ensemble des programmes de test, scripts et rapports permettant de reproduire ce
travail est fourni dans le dossier `tests/`, afin que chacun puisse vérifier comment
chaque entrée des tables a été établie.

Les fonctionnalités d'un programme, un langage de programmation et le format de
fichiers de données sont des idées et principes qui ne sont pas, en tant que tels,
protégés par le droit d'auteur (directive 2009/24/CE, considérant 11 et art. 5.3 ;
CJUE, 2 mai 2012, *SAS Institute*, C-406/10). Le droit de l'utilisateur légitime
d'observer, d'étudier ou de tester le fonctionnement d'un logiciel afin de déterminer
les idées et principes qui en sont à la base ne peut être écarté par contrat
(art. L.122-6-1 III et V du Code de la propriété intellectuelle ; directive
2009/24/CE, art. 5.3 et 8).

### 5. Responsabilité de l'utilisateur

En utilisant ce logiciel, vous acceptez :

* de ne l'utiliser **que sur des programmes dont vous êtes titulaire ou que vous êtes
  autorisé à maintenir**, cette vérification relevant de votre seule responsabilité ;
* de respecter les contrats de licence qui vous lient et les lois qui vous sont
  applicables, lesquelles peuvent différer du droit français ou européen ;
* de ne pas l'utiliser pour porter atteinte aux droits de propriété intellectuelle,
  aux secrets d'affaires ou aux engagements contractuels de quiconque ;
* que le code reconstitué **n'est pas garanti exact** : vous devez le relire et le
  valider sur simulateur avant tout usage sur un équipement réel. **Un robot
  industriel peut causer la mort, des blessures graves et des dégâts** ; le respect
  des normes et procédures de sécurité applicables (ISO 10218, analyse de risques,
  personnel qualifié…) reste de votre responsabilité.

### 6. Absence de garantie — limitation de responsabilité

Le logiciel est fourni **« en l'état », sans garantie d'aucune sorte**, expresse ou
implicite, notamment de qualité marchande, d'adéquation à un usage particulier,
d'exactitude ou d'absence de contrefaçon. Dans toute la mesure permise par la loi,
l'auteur ne saurait être tenu responsable d'aucun dommage direct ou indirect, perte de
production, perte de données, blessure ou réclamation résultant de l'utilisation ou de
l'impossibilité d'utiliser ce logiciel ou ses résultats. Lorsque la loi n'autorise pas
une telle exclusion, la responsabilité est limitée au minimum légal.

### 7. Titulaires de droits

Si vous êtes titulaire de droits et estimez qu'un élément de ce dépôt y porte
atteinte, ouvrez un ticket ou contactez l'auteur en précisant l'élément concerné et le
droit invoqué. Toute demande raisonnable sera examinée rapidement et de bonne foi, et
l'élément sera retiré ou modifié si la demande est fondée.
