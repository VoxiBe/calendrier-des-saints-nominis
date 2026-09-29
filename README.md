# Calendrier Nominis récurrent

Calendrier ICS récurrent basé sur les données de [Nominis](https://nominis.cef.fr/), regroupé par jour et compatible avec les applications utilisant le format iCalendar / CalDAV.

Le projet fournit également un script Python permettant de convertir un calendrier annuel Nominis en calendrier récurrent.

## Pourquoi ce projet ?

Les calendriers ICS proposés par Nominis sont générés année par année.

Chaque fête est donc enregistrée comme un événement indépendant. Par exemple, une fête présente le 2 janvier 2026 n'est pas définie comme une occurrence annuelle qui se répétera automatiquement en 2027, 2028, etc.

Ce projet transforme ces événements en véritables événements récurrents :

```text
RRULE:FREQ=YEARLY
```

Les différentes fêtes présentes le même jour sont également regroupées dans un seul événement afin d'obtenir un calendrier plus lisible.

Par exemple :

```text
Saint Basile le Grand • Saint Grégoire de Nazianze
```

Les informations complémentaires et les liens vers les fiches Nominis sont conservés dans la description de l'événement.

## Fichier prêt à l'emploi

Le fichier `nominis_recurrent_regroupe.ics` contient le calendrier déjà converti et peut être importé directement dans une application compatible ICS ou dans un serveur CalDAV.

Il a notamment été testé avec :

- [Radicale](https://radicale.org/) ([GitHub](https://github.com/Kozea/Radicale))
- [DAVx⁵](https://www.davx5.com/) ([GitHub](https://github.com/bitfireAT/davx5-ose))
- [Fossify Calendar](https://www.fossify.org/) ([GitHub](https://github.com/FossifyOrg/Calendar))

Par exemple, un calendrier hébergé dans Radicale peut être synchronisé sur Android avec DAVx⁵, puis affiché dans Fossify Calendar. 
Plus simplement, le fichier ICS peut aussi être importé localement dans n'importe quelle application prenant en charge le format iCalendar, comme Fossify Calendar, Microsoft Outlook, Mozilla Thunderbird ou Apple Calendar.

## Utilisation du script

### Prérequis

[Python 3](https://www.python.org/) ([GitHub](https://github.com/python/cpython)) est nécessaire.

Téléchargez d'abord un calendrier annuel au format ICS depuis Nominis :

https://nominis.cef.fr/contenus/telechargement.html

Placez ensuite le fichier téléchargé dans le même dossier que :

```text
convertir_nominis.py
```

Puis exécutez :

```bash
python convertir_nominis.py nominis2026.ics
```

Sous Windows, la commande peut également être :

```powershell
py convertir_nominis.py nominis2026.ics
```

Le script génère :

```text
nominis_recurrent_regroupe.ics
```

## Fonctionnement

Le script :

- regroupe les différentes fêtes présentes le même jour ;
- conserve les noms des saints et célébrations dans le titre ;
- conserve les informations détaillées et les liens Nominis dans la description ;
- transforme les événements fixes en récurrences annuelles ;
- génère un UID stable pour chaque journée ;
- exclut les événements explicitement liés à une année ;
- exclut certaines célébrations liturgiques mobiles afin de ne pas les transformer à tort en événements à date fixe ;
- vérifie le nombre d'événements, les UID et les récurrences avant de produire le fichier final.

## Exemple

Calendrier Nominis d'origine :

```text
Saint Basile le Grand - Moine, évêque de Césarée de Cappadoce, docteur de l'Église (+ 379)

Saint Grégoire de Nazianze - Patriarche de Constantinople, docteur de l'Église (+ 390)
```

Calendrier généré :

```text
Saint Basile le Grand • Saint Grégoire de Nazianze
```

Les descriptions complètes et les liens vers Nominis restent accessibles dans la description de l'événement.

## Limitations

- Les fêtes dont la date dépend de l'année, notamment certaines célébrations liées à Pâques, ne doivent pas être converties en simple récurrence annuelle à date fixe.

- Le script tente donc de détecter ces célébrations mobiles et de les exclure automatiquement.

- Un calendrier provenant d'une année non bissextile ne contient pas le 29 février. Les fêtes éventuellement associées à cette date ne peuvent donc pas être générées à partir d'un tel fichier source.

## Source des données

Les données calendaires proviennent de :

**Nominis — Conférence des évêques de France**

https://nominis.cef.fr/

Ce projet est indépendant et n'est ni affilié à Nominis ni officiellement soutenu par Nominis ou la Conférence des évêques de France.

Les liens vers les fiches Nominis d'origine sont conservés dans le calendrier généré.

## Licence

Le script et le code propres à ce projet sont distribués sous licence MIT.

Cette licence ne prétend pas modifier les droits applicables aux données provenant de Nominis.
