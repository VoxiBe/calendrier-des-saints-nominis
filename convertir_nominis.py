#!/usr/bin/env python3
"""
Convertit un calendrier annuel Nominis (.ics) en calendrier récurrent regroupé.

Fonctionnement :
- regroupe toutes les entrées d'une même date dans un seul événement ;
- conserve les noms des saints/célébrations dans le titre ;
- conserve les intitulés complets et les liens Nominis dans la description ;
- ajoute RRULE:FREQ=YEARLY ;
- exclut les événements dont le titre est explicitement lié à une année ;
- exclut une liste conservatrice de célébrations liturgiques mobiles afin de ne
  pas les figer à tort sur la date de l'année source.

Exemple :
    python convertir_nominis.py nominis2026.ics

Sortie par défaut :
    nominis_recurrent_regroupe.ics
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path


def unfold_ical(text: str) -> str:
    """Déplie les lignes iCalendar continuées (RFC 5545)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    unfolded = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return "\n".join(unfolded)


def get_prop(block: str, name: str) -> str | None:
    """Lit une propriété iCalendar simple dans un bloc VEVENT."""
    match = re.search(rf"^{re.escape(name)}(?:;[^:]*)?:(.*)$", block, flags=re.M)
    return match.group(1) if match else None


def unescape_ical_text(value: str | None) -> str:
    if value is None:
        return ""
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def escape_ical_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_ical_line(line: str, limit: int = 75) -> str:
    """
    Replie une ligne iCalendar à environ 75 octets.
    Les lignes de continuation commencent par un espace.
    """
    parts = []
    current = ""
    current_bytes = 0

    for char in line:
        size = len(char.encode("utf-8"))
        if current and current_bytes + size > limit:
            parts.append(current)
            current = " " + char
            current_bytes = 1 + size
        else:
            current += char
            current_bytes += size

    if current:
        parts.append(current)

    return "\r\n".join(parts)


def extract_events(text: str) -> list[str]:
    return re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, flags=re.S)


# Célébrations mobiles qu'il ne faut pas transformer en récurrence annuelle
# à date fixe. La comparaison se fait uniquement sur le "titre court"
# (la partie avant " - "), afin d'éviter les faux positifs dans les biographies.
#
# Cette liste est volontairement conservatrice. Dans le fichier Nominis 2026
# analysé, "Vendredi Saint" est la seule célébration de cette liste présente.
FETES_MOBILES = (
    "mercredi des cendres",
    "dimanche des rameaux",
    "jeudi saint",
    "vendredi saint",
    "paques",
    "lundi de paques",
    "ascension",
    "pentecote",
    "lundi de pentecote",
    "sainte trinite",
    "fete-dieu",
    "saint-sacrement",
    "sacre-coeur",
    "christ roi",
)


def normaliser_texte(value: str) -> str:
    """Normalise accents, casse, apostrophes et tirets pour les comparaisons."""
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def detecter_fete_mobile(titre_court: str) -> str | None:
    """
    Retourne le motif de fête mobile détecté, sinon None.

    On teste seulement le titre court. Ainsi une biographie contenant par
    exemple "religieuse du Sacré-Coeur" ne sera pas exclue.
    """
    titre = normaliser_texte(titre_court)
    for motif in FETES_MOBILES:
        motif_norm = normaliser_texte(motif)
        if titre == motif_norm or titre.startswith(motif_norm + " "):
            return motif
    return None


def parse_source(path: Path) -> tuple[dict[str, list[dict]], list[tuple[str, str, str]], str]:
    raw = path.read_text(encoding="utf-8-sig")
    text = unfold_ical(raw)
    events = extract_events(text)

    if not events:
        raise ValueError("Aucun bloc VEVENT trouvé dans le fichier.")

    grouped: dict[str, list[dict]] = defaultdict(list)
    excluded: list[tuple[str, str, str]] = []
    years_seen: set[str] = set()

    for block in events:
        dtstart_raw = get_prop(block, "DTSTART")
        summary_raw = get_prop(block, "SUMMARY")
        description_raw = get_prop(block, "DESCRIPTION")
        uid = get_prop(block, "UID") or ""

        if not dtstart_raw or not summary_raw:
            continue

        date_match = re.search(r"(\d{8})", dtstart_raw)
        if not date_match:
            continue

        ymd = date_match.group(1)
        year = ymd[:4]
        mmdd = ymd[4:]
        years_seen.add(year)

        summary = unescape_ical_text(summary_raw).strip()

        # Le titre court correspond à la partie avant le séparateur biographique.
        short_name = summary.split(" - ", 1)[0].strip()

        # 1) Exclusion des titres explicitement liés à une date/année.
        #    On n'exclut PAS les années biographiques des saints (+ 1947, etc.).
        mois = (
            "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
            "septembre|octobre|novembre|décembre|decembre"
        )
        evenement_date = re.search(
            rf"\b\d{{1,2}}\s+(?:{mois})\s+\d{{4}}\b|\ben\s+\d{{4}}\b",
            summary,
            flags=re.I,
        )
        if evenement_date:
            excluded.append((ymd, summary, "titre lié explicitement à une année"))
            continue

        # 2) Exclusion des célébrations liturgiques mobiles connues.
        fete_mobile = detecter_fete_mobile(short_name)
        if fete_mobile:
            excluded.append(
                (ymd, summary, f"célébration mobile détectée : {fete_mobile}")
            )
            continue

        description = unescape_ical_text(description_raw)
        link_match = re.search(
            r"https://nominis\.cef\.fr/contenus/saint/\S+",
            description,
        )
        permanent_url = link_match.group(0).strip() if link_match else ""

        grouped[mmdd].append(
            {
                "short": short_name,
                "full": summary,
                "url": permanent_url,
                "source_uid": uid,
                "source_date": ymd,
            }
        )

    if len(years_seen) != 1:
        raise ValueError(
            "Le fichier doit représenter une seule année. "
            f"Années détectées : {', '.join(sorted(years_seen)) or 'aucune'}"
        )

    source_year = next(iter(years_seen))
    return grouped, excluded, source_year


def build_calendar(
    grouped: dict[str, list[dict]],
    source_year: str,
    calendar_name: str,
) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Calendrier Nominis récurrent//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + escape_ical_text(calendar_name),
        "X-WR-CALDESC:" + escape_ical_text(
            "Calendrier Nominis regroupé par jour et converti en récurrences annuelles."
        ),
    ]

    for mmdd in sorted(grouped):
        items = grouped[mmdd]
        start = source_year + mmdd

        try:
            start_dt = datetime.strptime(start, "%Y%m%d")
        except ValueError as exc:
            raise ValueError(f"Date invalide dans la source : {start}") from exc

        end = (start_dt + timedelta(days=1)).strftime("%Y%m%d")

        title = " • ".join(item["short"] for item in items)

        description_parts = []
        for item in items:
            part = item["full"]
            if item["url"]:
                part += "\n" + item["url"]
            description_parts.append(part)

        description = "\n\n".join(description_parts)
        uid = f"nominis-{mmdd}-regroupe@local"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART;VALUE=DATE:{start}",
                f"DTEND;VALUE=DATE:{end}",
                "RRULE:FREQ=YEARLY",
                "CLASS:PUBLIC",
                "TRANSP:TRANSPARENT",
                "X-MICROSOFT-CDO-ALLDAYEVENT:TRUE",
                "SUMMARY:" + escape_ical_text(title),
                "DESCRIPTION:" + escape_ical_text(description),
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_ical_line(line) for line in lines) + "\r\n"


def validate_output(text: str, expected_dates: int) -> None:
    unfolded = unfold_ical(text)
    event_count = unfolded.count("BEGIN:VEVENT")
    rrule_count = unfolded.count("RRULE:FREQ=YEARLY")
    uids = re.findall(r"^UID:(.+)$", unfolded, flags=re.M)
    dates = re.findall(r"^DTSTART;VALUE=DATE:(\d{8})$", unfolded, flags=re.M)

    if event_count != expected_dates:
        raise ValueError(
            f"Validation échouée : {event_count} événements générés, "
            f"{expected_dates} attendus."
        )
    if rrule_count != event_count:
        raise ValueError("Validation échouée : certains événements ne sont pas récurrents.")
    if len(uids) != len(set(uids)):
        raise ValueError("Validation échouée : UID dupliqués.")
    if len(dates) != len(set(dates)):
        raise ValueError("Validation échouée : dates dupliquées.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convertit un calendrier annuel Nominis en calendrier ICS "
            "récurrent, avec un événement regroupé par jour."
        )
    )
    parser.add_argument("source", type=Path, help="Fichier Nominis .ics à convertir")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("nominis_recurrent_regroupe.ics"),
        help="Fichier de sortie (défaut : nominis_recurrent_regroupe.ics)",
    )
    parser.add_argument(
        "--nom",
        default="Fêtes et saints — Nominis",
        help="Nom du calendrier dans le fichier ICS",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Erreur : fichier introuvable : {args.source}", file=sys.stderr)
        return 1

    try:
        grouped, excluded, source_year = parse_source(args.source)
        result = build_calendar(grouped, source_year, args.nom)
        validate_output(result, len(grouped))
        args.output.write_text(result, encoding="utf-8", newline="")
    except Exception as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1

    print(f"Source : {args.source}")
    print(f"Année source : {source_year}")
    print(f"Dates générées : {len(grouped)}")
    print(f"Événements récurrents générés : {len(grouped)}")
    print(f"Entrées Nominis regroupées : {sum(len(items) for items in grouped.values())}")
    print(f"Entrées exclues : {len(excluded)}")

    for date, summary, raison in excluded:
        print(f"  - {date} : {summary}")
        print(f"    Raison : {raison}")

    if "0229" not in grouped:
        print(
            "Note : aucun 29 février n'était présent dans le fichier source. "
            "Une source issue d'une année bissextile est nécessaire pour l'inclure."
        )

    print(f"Fichier créé : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
