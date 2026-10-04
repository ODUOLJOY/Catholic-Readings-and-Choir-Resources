"""Official Catholic Church hierarchy data for Kenya.

PROVENANCE AND DATA POLICY
==========================
Every record carries ``source_url`` / ``source_name`` and a ``verification_status``
so we always know how a row entered the database.

Sources, in priority order:

1. KCCB official diocesan registry -- https://kccb.or.ke/dioceses/
   Authoritative for provinces, dioceses and archdioceses.
2. Official archdiocese / diocese websites.
3. KCCB / CIRDE official Church sources.

Records that could not be confirmed against an official source are NOT
fabricated. They are either omitted, or carried with
``verification_status = INCOMPLETE`` / ``NEEDS_REVIEW``.

Stable machine-readable codes
-----------------------------
Codes are the importer's primary key and are derived hierarchically::

    KE                                     country
    KE-NRB                                 ecclesiastical province
    KE-NRB-NBI                             archdiocese / diocese
    KE-NRB-NBI-CENTRAL                     deanery
    KE-NRB-NBI-CENTRAL-HOLY-FAMILY         parish

Display names are never used as primary keys.

Military Ordinariate
--------------------
The Military Ordinariate is a personal ordinariate of the Holy See, not a
territorial diocese. It has no province, no deaneries and no parishes in this
hierarchy, and is excluded from the geographic cascade. It is kept here so the
jurisdiction registry remains complete and auditable.

Provenance dates
----------------
``VERIFIED_ON`` records when the source was read for this import.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

VERIFIED_ON = "2026-10-02"

KCCB_DIOCESES_URL = "https://kccb.or.ke/dioceses/"
KCCB_ORG_URL = "https://kccb.or.ke/kccb/"

VERIFIED = "VERIFIED"
NEEDS_REVIEW = "NEEDS_REVIEW"
INCOMPLETE = "INCOMPLETE"

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")


def slugify(value: str) -> str:
    """Return a deterministic uppercase code fragment for ``value``.

    Handles curly apostrophes, ampersands and accented characters so that
    ``St. Peter's Parish`` -> ``ST-PETER-S-PARISH``.
    """
    normalised = unicodedata.normalize("NFKD", value)
    ascii_text = normalised.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("&", " AND ")
    code = _NON_ALNUM.sub("-", ascii_text.upper()).strip("-")
    return code or "UNNAMED"


def parish_code(deanery_code: str, parish_name: str) -> str:
    """Stable parish code, derived from its deanery code and name."""
    return f"{deanery_code}-{slugify(parish_name)}"


COUNTRIES = [
    {
        "code": "KE",
        "name": "Kenya",
        "source_url": KCCB_ORG_URL,
        "source_name": "Kenya Conference of Catholic Bishops (KCCB)",
        "verification_status": VERIFIED,
    },
]

# name, code, short_name, metropolitan_diocese_code
PROVINCES = [
    {
        "code": "KE-NRB",
        "name": "Ecclesiastical Province of Nairobi",
        "short_name": "Nairobi",
        "country_code": "KE",
        "metropolitan_code": "KE-NRB-NBI",
        "source_url": KCCB_DIOCESES_URL,
        "source_name": "KCCB diocesan registry",
        "verification_status": VERIFIED,
    },
    {
        "code": "KE-NRY",
        "name": "Ecclesiastical Province of Nyeri",
        "short_name": "Nyeri",
        "country_code": "KE",
        "metropolitan_code": "KE-NRY-NYR",
        "source_url": KCCB_DIOCESES_URL,
        "source_name": "KCCB diocesan registry",
        "verification_status": VERIFIED,
    },
    {
        "code": "KE-KSM",
        "name": "Ecclesiastical Province of Kisumu",
        "short_name": "Kisumu",
        "country_code": "KE",
        "metropolitan_code": "KE-KSM-KSM",
        "source_url": KCCB_DIOCESES_URL,
        "source_name": "KCCB diocesan registry",
        "verification_status": VERIFIED,
    },
    {
        "code": "KE-MBA",
        "name": "Ecclesiastical Province of Mombasa",
        "short_name": "Mombasa",
        "country_code": "KE",
        "metropolitan_code": "KE-MBA-MBA",
        "source_url": KCCB_DIOCESES_URL,
        "source_name": "KCCB diocesan registry",
        "verification_status": VERIFIED,
    },
]

# code, name, short_name, province_code, is_archdiocese, erected_on, official_site
DIOCESES = [
    # --- Ecclesiastical Province of Nairobi -----------------------------------
    ("KE-NRB-NBI", "Archdiocese of Nairobi", "Nairobi", "KE-NRB", True, "26-02-1860",
     "https://archdioceseofnairobi.org"),
    ("KE-NRB-KTI", "Diocese of Kitui", "Kitui", "KE-NRB", False, "20-02-1954",
     "https://dioceseofkitui.org"),
    ("KE-NRB-MKS", "Diocese of Machakos", "Machakos", "KE-NRB", False, "20-01-1964", None),
    ("KE-NRB-NKR", "Diocese of Nakuru", "Nakuru", "KE-NRB", False, "11-01-1968", None),
    ("KE-NRB-NGO", "Diocese of Ngong", "Ngong", "KE-NRB", False, "11-01-1968",
     "https://www.dioceseofngong.org"),
    ("KE-NRB-KRC", "Diocese of Kericho", "Kericho", "KE-NRB", False, "06-12-1995", None),
    ("KE-NRB-WTE", "Diocese of Wote", "Wote", "KE-NRB", False, "22-07-2023", None),
    # --- Ecclesiastical Province of Nyeri ------------------------------------
    ("KE-NRY-NYR", "Archdiocese of Nyeri", "Nyeri", "KE-NRY", True, "14-12-1905",
     "https://www.adnyeri.org"),
    ("KE-NRY-MER", "Diocese of Meru", "Meru", "KE-NRY", False, "10-03-1926",
     "https://catholicdioceseofmeru.org"),
    ("KE-NRY-MSB", "Diocese of Marsabit", "Marsabit", "KE-NRY", False, "25-11-1964",
     "https://marsabitdiocese.org"),
    ("KE-NRY-MRG", "Diocese of Murang'a", "Murang'a", "KE-NRY", False, "17-03-1983",
     "https://catholicdioceseofmuranga.org"),
    ("KE-NRY-EMB", "Diocese of Embu", "Embu", "KE-NRY", False, "09-06-1986", None),
    ("KE-NRY-NYH", "Diocese of Nyahururu", "Nyahururu", "KE-NRY", False, "15-06-2001", None),
    ("KE-NRY-MRL", "Diocese of Maralal", "Maralal", "KE-NRY", False, "05-12-2002", None),
    ("KE-NRY-ISL", "Diocese of Isiolo", "Isiolo", "KE-NRY", False, "15-02-2023",
     "https://cdisiolo.org"),
    # --- Ecclesiastical Province of Kisumu -----------------------------------
    ("KE-KSM-KSM", "Archdiocese of Kisumu", "Kisumu", "KE-KSM", True, "15-07-1925", None),
    ("KE-KSM-ELD", "Diocese of Eldoret", "Eldoret", "KE-KSM", False, "29-06-1953",
     "https://www.cde.co.ke"),
    ("KE-KSM-KSI", "Diocese of Kisii", "Kisii", "KE-KSM", False, "21-05-1960", None),
    ("KE-KSM-LOD", "Diocese of Lodwar", "Lodwar", "KE-KSM", False, "11-01-1968",
     "https://dioceseoflodwar.org"),
    ("KE-KSM-KAK", "Diocese of Kakamega", "Kakamega", "KE-KSM", False, "27-02-1978", None),
    ("KE-KSM-BUN", "Diocese of Bungoma", "Bungoma", "KE-KSM", False, "27-04-1987", None),
    ("KE-KSM-HBY", "Diocese of Homa Bay", "Homa Bay", "KE-KSM", False, "18-10-1993",
     "https://cdohb.or.ke"),
    ("KE-KSM-KTL", "Diocese of Kitale", "Kitale", "KE-KSM", False, "03-04-1998",
     "https://catholickitale.org"),
    ("KE-KSM-KAP", "Diocese of Kapsabet", "Kapsabet", "KE-KSM", False, "10-07-2025", None),
    # --- Ecclesiastical Province of Mombasa ----------------------------------
    ("KE-MBA-MBA", "Archdiocese of Mombasa", "Mombasa", "KE-MBA", True, "08-04-1955",
     "https://mombasacatholic.org"),
    ("KE-MBA-GRS", "Diocese of Garissa", "Garissa", "KE-MBA", False, "09-12-1976",
     "https://garissacatholic.org"),
    ("KE-MBA-MLD", "Diocese of Malindi", "Malindi", "KE-MBA", False, "02-06-2000",
     "https://www.malindicatholicdiocese.org"),
]

# The Military Ordinariate has no province and no deanery/parish cascade.
MILITARY_ORDINARIATE = {
    "code": "KE-MIL-ORD",
    "name": "Military Ordinariate",
    "short_name": "Military Ordinariate",
    "province_code": None,
    "is_archdiocese": False,
    "is_military_ordinariate": True,
    "erected_on": "29-05-1969",
    "website": None,
}


def _diocese(code, name, short_name, province_code, is_archdiocese, erected_on, website):
    return {
        "code": code,
        "name": name,
        "short_name": short_name,
        "province_code": province_code,
        "is_archdiocese": is_archdiocese,
        "is_military_ordinariate": False,
        "erected_on": erected_on,
        "website": website,
        "source_url": KCCB_DIOCESES_URL,
        "source_name": "KCCB diocesan registry",
        "verification_status": VERIFIED,
    }


ALL_DIOCESES = [_diocese(*row) for row in DIOCESES] + [
    {
        **MILITARY_ORDINARIATE,
        "source_url": KCCB_DIOCESES_URL,
        "source_name": "KCCB diocesan registry",
        "verification_status": VERIFIED,
    },
]

# ---------------------------------------------------------------------------
# Deaneries
# ---------------------------------------------------------------------------
# (diocese_code, deanery_name, source_url, verification_status)

ADN = "https://archdioceseofnairobi.org"

DEANERY_ROWS = [
    # Archdiocese of Nairobi -- official per-deanery pages. 17 deaneries.
    ("KE-NRB-NBI", "Embakasi Deanery", f"{ADN}/?page_id=4665", VERIFIED),
    ("KE-NRB-NBI", "Gatundu Deanery", f"{ADN}/?page_id=4671", VERIFIED),
    ("KE-NRB-NBI", "Githunguri Deanery", f"{ADN}/?page_id=4672", VERIFIED),
    ("KE-NRB-NBI", "Githurai Deanery", f"{ADN}/?page_id=6928", VERIFIED),
    ("KE-NRB-NBI", "Kabete Deanery", f"{ADN}/?page_id=6588", VERIFIED),
    ("KE-NRB-NBI", "Kiambu Deanery", f"{ADN}/?page_id=4674", VERIFIED),
    ("KE-NRB-NBI", "Kikuyu Deanery", f"{ADN}/?page_id=4673", VERIFIED),
    ("KE-NRB-NBI", "Limuru Deanery", f"{ADN}/?page_id=4675", VERIFIED),
    ("KE-NRB-NBI", "Makadara Deanery", f"{ADN}/?page_id=4667", VERIFIED),
    ("KE-NRB-NBI", "Mang'u Deanery", f"{ADN}/?page_id=4670", VERIFIED),
    ("KE-NRB-NBI", "Nairobi Central Deanery", f"{ADN}/?page_id=4623", VERIFIED),
    ("KE-NRB-NBI", "Nairobi-Western Deanery", f"{ADN}/?page_id=4664", VERIFIED),
    ("KE-NRB-NBI", "Outering Deanery", f"{ADN}/?page_id=4668", VERIFIED),
    ("KE-NRB-NBI", "Ruaraka Deanery", f"{ADN}/?page_id=4666", VERIFIED),
    ("KE-NRB-NBI", "Ruai Deanery", f"{ADN}/?page_id=7497", VERIFIED),
    ("KE-NRB-NBI", "Ruiru Deanery", f"{ADN}/?page_id=5097", VERIFIED),
    ("KE-NRB-NBI", "Thika Deanery", f"{ADN}/?page_id=4669", VERIFIED),

    # Ngong -- official site navigation / parishes page
    ("KE-NRB-NGO", "Kilgoris Deanery", "https://www.dioceseofngong.org", VERIFIED),
    ("KE-NRB-NGO", "Ololulunga Deanery", "https://www.dioceseofngong.org", VERIFIED),
    ("KE-NRB-NGO", "Narok Deanery", "https://www.dioceseofngong.org", VERIFIED),
    ("KE-NRB-NGO", "Ngong Deanery", "https://www.dioceseofngong.org", VERIFIED),
    ("KE-NRB-NGO", "Kiserian Deanery", "https://www.dioceseofngong.org", VERIFIED),
    ("KE-NRB-NGO", "Kajiado Deanery", "https://www.dioceseofngong.org", VERIFIED),
    ("KE-NRB-NGO", "Oloitokitok Deanery", "https://www.dioceseofngong.org", VERIFIED),

    # Kitui -- official parishes page, grouped under six deaneries
    ("KE-NRB-KTI", "Northern Deanery", "https://dioceseofkitui.org/parishes", VERIFIED),
    ("KE-NRB-KTI", "Western Deanery", "https://dioceseofkitui.org/parishes", VERIFIED),
    ("KE-NRB-KTI", "Central Deanery", "https://dioceseofkitui.org/parishes", VERIFIED),
    ("KE-NRB-KTI", "Southern Deanery", "https://dioceseofkitui.org/parishes", VERIFIED),
    ("KE-NRB-KTI", "Yatta Deanery", "https://dioceseofkitui.org/parishes", VERIFIED),
    ("KE-NRB-KTI", "Eastern Deanery", "https://dioceseofkitui.org/parishes", VERIFIED),

    # Nyeri -- official site menu
    ("KE-NRY-NYR", "Nyeri Municipality Deanery", "https://www.adnyeri.org", VERIFIED),
    ("KE-NRY-NYR", "Narumoru Deanery", "https://www.adnyeri.org", VERIFIED),
    ("KE-NRY-NYR", "Tetu Deanery", "https://www.adnyeri.org", VERIFIED),
    ("KE-NRY-NYR", "Othaya Deanery", "https://www.adnyeri.org", VERIFIED),
    ("KE-NRY-NYR", "Nanyuki Deanery", "https://www.adnyeri.org", VERIFIED),
    ("KE-NRY-NYR", "Karatina Deanery", "https://www.adnyeri.org", VERIFIED),
    ("KE-NRY-NYR", "Gatarakwa Deanery", "https://www.adnyeri.org", VERIFIED),
    ("KE-NRY-NYR", "Mukurwe-ini Deanery", "https://www.adnyeri.org", VERIFIED),

    # Meru -- official site states 8 deaneries
    ("KE-NRY-MER", "Igembe Deanery", "https://catholicdioceseofmeru.org", VERIFIED),
    ("KE-NRY-MER", "Tigania Deanery", "https://catholicdioceseofmeru.org", VERIFIED),
    ("KE-NRY-MER", "Buuri Deanery", "https://catholicdioceseofmeru.org", VERIFIED),
    ("KE-NRY-MER", "Imenti North Deanery", "https://catholicdioceseofmeru.org", VERIFIED),
    ("KE-NRY-MER", "Imenti Central Deanery", "https://catholicdioceseofmeru.org", VERIFIED),
    ("KE-NRY-MER", "South Imenti Deanery", "https://catholicdioceseofmeru.org", VERIFIED),
    ("KE-NRY-MER", "Maara Deanery", "https://catholicdioceseofmeru.org", VERIFIED),
    ("KE-NRY-MER", "Tharaka Deanery", "https://catholicdioceseofmeru.org", VERIFIED),

    # Murang'a -- 8 deaneries from official site menu
    ("KE-NRY-MRG", "Baricho Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),
    ("KE-NRY-MRG", "Gatanga Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),
    ("KE-NRY-MRG", "Gaichanjiru Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),
    ("KE-NRY-MRG", "Kianyaga Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),
    ("KE-NRY-MRG", "Maragua Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),
    ("KE-NRY-MRG", "Murang'a Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),
    ("KE-NRY-MRG", "Mwea Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),
    ("KE-NRY-MRG", "Tuthu Deanery", "https://catholicdioceseofmuranga.org", VERIFIED),

    # Mombasa -- official page states 12 deaneries and names them
    ("KE-MBA-MBA", "Central Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "North Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "West Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "South Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Kilifi Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Kwale East Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Kwale West Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Taita Taveta Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Giriama Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Voi Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Wunganyi Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),
    ("KE-MBA-MBA", "Bura Deanery", "https://mombasacatholic.org/index.php/deaneries", VERIFIED),

    # Kitale -- official site states 7 deaneries
    ("KE-KSM-KTL", "Cathedral Deanery", "https://catholickitale.org", VERIFIED),
    ("KE-KSM-KTL", "Kolongolo Deanery", "https://catholickitale.org", VERIFIED),
    ("KE-KSM-KTL", "Kiminini Deanery", "https://catholickitale.org", VERIFIED),
    ("KE-KSM-KTL", "Suwerwa Deanery", "https://catholickitale.org", VERIFIED),
    ("KE-KSM-KTL", "Tartar Deanery", "https://catholickitale.org", VERIFIED),
    ("KE-KSM-KTL", "Kapenguria Deanery", "https://catholickitale.org", VERIFIED),
    ("KE-KSM-KTL", "Ortun Deanery", "https://catholickitale.org", VERIFIED),
]


def _deanery(diocese_code, name, source_url, verification_status):
    return {
        "code": f"{diocese_code}-{slugify(name.removesuffix('Deanery').strip())}",
        "name": name,
        "diocese_code": diocese_code,
        "source_url": source_url,
        "source_name": "Official diocesan/archdiocesan website",
        "verification_status": verification_status,
    }


DEANERIES = [_deanery(*row) for row in DEANERY_ROWS]

# ---------------------------------------------------------------------------
# Parishes
# ---------------------------------------------------------------------------
# Only the Archdiocese of Nairobi publishes a complete deanery -> parish listing
# on its official site. Every other diocese is left at deanery level with the
# deanery marked VERIFIED and its parishes pending an official listing.
#
# Nairobi: 17 deaneries / 127 parishes, matching the figure the Archdiocese
# itself publishes on https://archdioceseofnairobi.org/

# (deanery name, parish name, address)
PARISH_ROWS = [
    ("Embakasi Deanery", "Divine Word Parish Kayole", "P.O Box, 433-00518 KAYOLE"),
    ("Embakasi Deanery", "St. Joachim & Anne Parish, Soweto", "P.O Box 11-00518 KAYOLE"),
    ("Embakasi Deanery", "Christ the King Parish, Embakasi", "P.O Box, 19157-00501 NAIROBI"),
    ("Embakasi Deanery", "St. Mary Immaculate Parish, Mihang'o", "P.O Box, 19-00518 KAYOLE"),
    ("Embakasi Deanery", "St. Daniel Comboni Parish, Utawala", None),
    ("Embakasi Deanery", "St. Arnold Janssen Parish, Komarock", None),

    ("Gatundu Deanery", "Our Lady of the Annunciation Parish, Gatitu", "P.O Box, 47-01030 GATUNDU"),
    ("Gatundu Deanery", "Martyrs of Uganda Parish, Gatundu", "P.O Box, 29-01030 GATUNDU"),
    ("Gatundu Deanery", "St. Stephen Parish, Ituuru (Chaplaincy)", "P.O Box, 256-01030 GATUNDU"),
    ("Gatundu Deanery", "Christ the King Parish, Karinga", "P.O Box, 273-01030 GATUNDU"),
    ("Gatundu Deanery", "St. Joseph the Worker Parish, Kiganjo", "P.O Box 659-01030 GATUNDU"),
    ("Gatundu Deanery", "Archangel Gabriel Parish, Mutomo", "P.O Box, 425-01030 GATUNDU"),
    ("Gatundu Deanery", "St. Joseph Parish, Mutunguru", "P.O Box, 785-01030 GATUNDU"),
    ("Gatundu Deanery", "Mary Help of Christians Parish, Ndundu", "P.O Box, 279-00232 RUIRU"),
    ("Gatundu Deanery", "St. John the Baptist Parish, Munyu-ini", "P.O Box 273-01030 GATUNDU"),

    ("Githunguri Deanery", "St. John Evangelist Parish Githiga", "P.O Box, 1107-00900 KIAMBU"),
    ("Githunguri Deanery", "Holy Family Parish Githunguri", "P.O Box, 9-00216 GITHUNGURI"),
    ("Githunguri Deanery", "Nativity of our Lady Parish Kagwe", "P.O Box, 265-00900 KIAMBU"),
    ("Githunguri Deanery", "Our Lady of the Assumption Parish Kambaa", "P. O Box, 436-00216 GITHUNGURI"),
    ("Githunguri Deanery", "All Saints Parish Komothai", "P.O Box, 213-00901 NGEWA"),
    ("Githunguri Deanery", "Holy Spirit Parish Miguta", "P.O Box 471-00216 GITHUNGURI"),
    ("Githunguri Deanery", "St. Theresa of the Child Jesus Parish Ngenya", "P.O Box 740-00216 GITHUNGURI"),

    ("Githurai Deanery", "Christ The King Parish Githurai Kimbo", "P.O Box, 818-00618 RUARAKA"),
    ("Githurai Deanery", "St. Joseph Parish Kahawa Sukari", "P.O Box, 16652-00620 NAIROBI"),
    ("Githurai Deanery", "St. Joseph Mukasa Parish, Kahawa West", "P.O Box, 65588-00607 KAMITI"),
    ("Githurai Deanery", "St. Francis of Assisi Parish Mwihoko", "P.O Box, 148-00626 GITHURAI"),
    ("Githurai Deanery", "Our Lady Consolata Catholic Parish Kahawa Farmers", "P.O Box, 65957-00607 NAIROBI"),
    ("Githurai Deanery", "St. Lucia Parish Membley", "P. O. Box, 1136-00900 KIAMBU"),
    ("Githurai Deanery", "Holy Mary Mother of God Parish Githurai", "P.O Box, 65109-00618 RUARAKA"),

    ("Kabete Deanery", "Our Lady of the Rosary Parish Ridgeways", "P.O. Box 39123-00623 NAIROBI"),
    ("Kabete Deanery", "St. Catherine of Sienna Parish Spring Valley", "P.O Box, 230-00621 VILLAGE MARKET"),
    ("Kabete Deanery", "St. Austin Parish Msongari", "P.O Box, 252-00606 SARIT CENTRE"),
    ("Kabete Deanery", "Consolata Shrine Parish Westlands", "P.O Box, 14930-00800 WESTLANDS"),
    ("Kabete Deanery", "Holy Trinity Parish, Kileleshwa", "P. O. Box 25732-00603 Lavington NAIROBI"),
    ("Kabete Deanery", "St. Joseph the Worker Parish, Kangemi", "P.O Box, 23408-00625 KANGEMI"),
    ("Kabete Deanery", "St. Raphael Kabete Parish, Kabete", "P.O Box, 23676-00625 NAIROBI"),

    ("Kiambu Deanery", "St. Stephen Parish, Gachie", "P.O Box, 1026-00621 VILLAGE MARKET"),
    ("Kiambu Deanery", "St. Joseph Parish, Gathanga", "P.O Box, 774-00219 KARURI"),
    ("Kiambu Deanery", "St. Martin de Porres Parish, Karuri", "P.O Box 78-00219 KARURI"),
    ("Kiambu Deanery", "Sts. Peter & Paul Parish, Kiambu", "P.O Box 8-00900 KIAMBU"),
    ("Kiambu Deanery", "Our Lady of Victories Parish, Lioki", "P.O Box 44-00900 KIAMBU"),
    ("Kiambu Deanery", "All Saints Parish, Riara", "P.O Box, 177-00900 KIAMBU"),
    ("Kiambu Deanery", "Our Lady of the Holy Rosary Parish, Ting'ang'a", "P.O Box, 601-00900 KIAMBU"),
    ("Kiambu Deanery", "Holy Rosary Parish, Ikinu", "P.O Box, 100-00900 KIAMBU"),
    ("Kiambu Deanery", "Holy Family Parish, Mugumo", "P.O Box, 2047-00900 KIAMBU"),

    ("Kikuyu Deanery", "Immaculate Conception Parish, Gicharani", "P.O Box, 404-00902 KIKUYU"),
    ("Kikuyu Deanery", "St. Peter the Apostle Parish, Kikuyu", "P.O Box, 888-00902 KIKUYU"),
    ("Kikuyu Deanery", "St. Charles Lwanga Parish, Waithaka", "P.O Box, 79024-00400 NAIROBI"),
    ("Kikuyu Deanery", "St. Joseph Parish, Muguga", "P.O Box, 731-00902 KIKUYU"),
    ("Kikuyu Deanery", "St. John the Baptist Parish, Riruta", "P.O Box, 21243-00512 NAIROBI"),
    ("Kikuyu Deanery", "Our Lady of the Rosary Parish, Ruku", "P.O Box, 23020-00604 LOWER KABETE"),
    ("Kikuyu Deanery", "Holy Rosary Parish, Thigio", "P.O Box, 200-00217 LIMURU"),
    ("Kikuyu Deanery", "St. Joseph Parish, Kerwa", "P.O Box, 1314-00217 LIMURU"),
    ("Kikuyu Deanery", "Holy Eucharist Parish, King'eero", "P.O Box, 23228-00604 LOWER KABETE"),
    ("Kikuyu Deanery", "St. Peter the Rock Parish, Kinoo", "P. O. Box, 419-00605 UTHIRU"),

    ("Limuru Deanery", "Our Lady of Mt. Carmel Parish, Ngarariga", "P.O Box, 220-00217 LIMURU"),
    ("Limuru Deanery", "St. Joseph the Worker Parish, Kereita", "P.O Box, 54-00222 UPLANDS"),
    ("Limuru Deanery", "St. Joseph Parish, Limuru", "P.O Box, 63-00217 LIMURU"),
    ("Limuru Deanery", "St. Francis Parish, Limuru", "P. O Box, 468-00217 LIMURU"),
    ("Limuru Deanery", "St. Charles Lwanga Parish, Kamirithu", "P.O Box, 457-00217 LIMURU"),
    ("Limuru Deanery", "St. Charles Lwanga Parish, Githirioni", "P.O Box 100-00222 UPLANDS"),
    ("Limuru Deanery", "St. Andrews Parish, Rironi", "P.O Box, 423, LIMURU"),

    ("Makadara Deanery", "Our Lady of Visitation Parish, Makadara", "P.O Box, 72661-00200 NAIROBI"),
    ("Makadara Deanery", "Blessed Sacrament Parish, Buruburu", "P.O Box, 42454-00515 BURUBURU"),
    ("Makadara Deanery", "Holy Trinity Parish, Buruburu", "P.O Box, 233-00515 BURUBURU"),
    ("Makadara Deanery", "St. Teresa's Parish, Eastleigh", "P.O Box, 42603-00610 EASTLEIGH"),
    ("Makadara Deanery", "Mary Magdalene Parish, Kariokor", "P.O Box, 41520-00100 NAIROBI"),
    ("Makadara Deanery", "St. Joseph Parish, Jericho", "P.O Box, 48069-00100 NAIROBI"),
    ("Makadara Deanery", "St. Joseph & Mary Parish, Shauri Moyo", "P.O Box, 17178-00510 MAKONGENI"),
    ("Makadara Deanery", "St. Mary's Parish, Mukuru", "P.O Box, 3232-00506 NYAYO STADIUM"),

    ("Mang'u Deanery", "St. Stephen Parish, Kairi", "P.O Box, 477-01007 KAIRI"),
    ("Mang'u Deanery", "Our Lady of the Holy Rosary Parish, Kamwangi", "P.O Box, 44-01004 KANJUKU"),
    ("Mang'u Deanery", "St. Teresa Parish, Kiangunu", "P.O Box, 2015-01000 THIKA"),
    ("Mang'u Deanery", "Our Lady of Fatima Parish, Kiriko", "P.O Box, 49-01000 THIKA"),
    ("Mang'u Deanery", "St. John the Baptist Parish, Mang'u", "P.O Box, 298-01000 THIKA"),
    ("Mang'u Deanery", "St. Anne's Parish, Mataara", "P.O Box, 650-01009 MATAARA"),
    ("Mang'u Deanery", "St. Peter Parish, Nyamang'ara", "P.O. Box 2629-01000 THIKA"),
    ("Mang'u Deanery", "St. Teresa of Avila Parish, Gachege", "P. O. Box 245-01004 KANJUKU"),

    ("Nairobi Central Deanery", "St. Paul's Chapel, University of Nairobi", "P.O Box, 41512-00100 NAIROBI"),
    ("Nairobi Central Deanery", "Holy Family Minor Basilica Parish", "P.O Box 40891-00100, NAIROBI"),
    ("Nairobi Central Deanery", "St. Peter Claver's Parish", "P.O Box 41065-00100, NAIROBI"),
    ("Nairobi Central Deanery", "St. Francis Xavier Parish, Parklands", "P.O Box, 14313-00623, PARKLANDS"),
    ("Nairobi Central Deanery", "Our Lady Queen of Peace Parish, South B", "P.O Box, 60311-00200, NAIROBI"),
    ("Nairobi Central Deanery", "St. Catherine of Alexandria Catholic Parish, South-C", "P.O Box, 3663-00506, NYAYO STADIUM"),
    ("Nairobi Central Deanery", "Shrine of Mary Help of Christians Parish, Upper Hill", "P.O Box, 62322-00200, NAIROBI"),

    ("Nairobi-Western Deanery", "Regina Caeli Parish, Karen", "P.O Box 24391-00502 KAREN"),
    ("Nairobi-Western Deanery", "St. Michael the Archangel Parish, Langata", "P.O Box 41418-00100 NAIROBI"),
    ("Nairobi-Western Deanery", "Christ The King Parish, Kibera", "P.O Box 21188-00505, NGONG RD"),
    ("Nairobi-Western Deanery", "Our Lady of Guadalupe Parish, Adams Arcade", "P.O Box 21245-00505 NGONG RD"),
    ("Nairobi-Western Deanery", "Sacred Heart Parish, Dagoretti", "P.O Box, 21200-00505 NGONG RD"),
    ("Nairobi-Western Deanery", "St. John the Evangelist Parish, Langata", "P.O Box, 15633-00509 LANGATA"),
    ("Nairobi-Western Deanery", "Mary Queen of Apostles Parish, Dagoretti", "P.O Box, 1182-00902, KIKUYU"),

    ("Outering Deanery", "St. Jude Parish, Donholm", "P.O. Box 53576-00100 NAIROBI"),
    ("Outering Deanery", "Assumption of Mary Parish, Umoja", "P.O Box, 30815-00100 NAIROBI"),
    ("Outering Deanery", "Divine Mercy Parish, Kariobangi", "P.O Box, 717-00515 BURUBURU"),
    ("Outering Deanery", "Holy Cross Parish, Dandora", "P.O Box, 58078-00200 NAIROBI"),
    ("Outering Deanery", "Holy Trinity Parish, Kariobangi", "P.O Box, 47714-00100 NAIROBI"),
    ("Outering Deanery", "Holy Innocents Parish, Tassia", "P. O Box, 60827-00200 NAIROBI"),
    ("Outering Deanery", "St. Andre Bessette Parish, Dandora", None),

    ("Ruaraka Deanery", "St. Clare Parish, Kasarani", "P.O Box, 65103-00618 RUARAKA"),
    ("Ruaraka Deanery", "Queen of Apostles Parish, Ruaraka", "P.O Box, 48409-00618 RUARAKA"),
    ("Ruaraka Deanery", "Sacred Heart Parish, Baba Dogo", "P.O Box, 65125-00618 RUARAKA VILLAGE MARKET"),
    ("Ruaraka Deanery", "St. Benedict Parish, Survey", "P.O Box, 32101-00600 NGARA RD"),
    ("Ruaraka Deanery", "St. Dominic Parish, Mwiki", "P.O.Box, 43684-00100 MWIKI"),
    ("Ruaraka Deanery", "Mother Theresa of Calcutta Parish, Zimmerman", "P. O. Box 1450, 00618 NAIROBI"),

    ("Ruai Deanery", "St. Joseph Freinademetz Parish Ruai", "P.O Box, 20546-00200 NAIROBI"),
    ("Ruai Deanery", "Holy Family Parish, Utawala", "P.O. Box, 1020-00521 NAIROBI"),
    ("Ruai Deanery", "St. Peter's Parish, Ruai", "P.O Box, 20546-00200 NAIROBI"),
    ("Ruai Deanery", "St. Vincent de Paul Parish, Kamulu", "P.O Box, 28021-00200 NAIROBI"),
    ("Ruai Deanery", "St. Monica Parish, Njiru", "P.O Box, 85-90115 NAIROBI"),
    ("Ruai Deanery", "St. John the Baptist Parish, Katua", None),

    ("Ruiru Deanery", "St. Christopher Parish, Kembo", "P. O. Box 1297-00232 RUIRU"),
    ("Ruiru Deanery", "St. Augustine Parish, JKUAT Chaplaincy", "P. O. Box, 62000-00200 NAIROBI"),
    ("Ruiru Deanery", "St. Francis of Assisi Parish, Ruiru", "P.O Box, 384-00232 RUIRU"),
    ("Ruiru Deanery", "St. Peter Parish, Kwihota", "P. O. Box 121-00232 RUIRU"),
    ("Ruiru Deanery", "Presentation of the Lord Parish, Juja Farm", "P. O. Box, 315-00232 RUIRU"),
    ("Ruiru Deanery", "St. Theresa Parish, Kalimoni", "P. O. Box 141-01001, KALIMONI"),
    ("Ruiru Deanery", "Mary Immaculate Parish, Kumura", "P.O Box, 1297-00232 RUIRU"),
    ("Ruiru Deanery", "Divine Mercy Parish, Kenyatta Road", None),
    ("Ruiru Deanery", "St. Paul Parish, Mugutha", None),

    ("Thika Deanery", "St. Matias Mulumba Parish, Thika", "P.O Box, 3395-01000 THIKA"),
    ("Thika Deanery", "St. Patrick's Parish, Thika", "P.O Box, 33-01000 THIKA"),
    ("Thika Deanery", "Maria Magdalene Parish, Munyu", "P.O Box, 3396-01000 THIKA"),
    ("Thika Deanery", "Immaculate Conception Parish, Kilimambogo", "P.O Box 187-01000 THIKA"),
    ("Thika Deanery", "St. Bernadette Parish, Ngoingwa", "P.O. Box, 1499 THIKA"),
    ("Thika Deanery", "St. Achilles Kiwanuka Parish, Thika", None),
    ("Thika Deanery", "Holy Rosary Parish, Witeithie", None),
]

_DEANERY_BY_NAME = {row["name"]: row for row in DEANERIES}


def build_parishes() -> list[dict]:
    """Return the parish rows, each resolved to its stable deanery code."""
    parishes: list[dict] = []
    for deanery_name, parish_name, address in PARISH_ROWS:
        deanery = _DEANERY_BY_NAME.get(deanery_name)
        if deanery is None:
            raise KeyError(f"Unknown deanery in parish data: {deanery_name}")
        parishes.append(
            {
                "code": parish_code(deanery["code"], parish_name),
                "name": parish_name,
                "deanery_code": deanery["code"],
                "diocese_code": deanery["diocese_code"],
                "address": address,
                "source_url": deanery["source_url"],
                "source_name": deanery["source_name"],
                "verification_status": VERIFIED,
            }
        )
    return parishes


PARISHES = build_parishes()


# ---------------------------------------------------------------------------
# Coverage reporting
# ---------------------------------------------------------------------------

# Dioceses whose official website does not currently publish a deanery
# breakdown. Their parishes remain unimported rather than fabricated.
DIOCESES_WITHOUT_OFFICIAL_DEANERY_DATA: dict[str, str] = {
    "KE-NRB-MKS": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-NRB-NKR": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-NRB-KRC": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-NRB-WTE": "Newly erected (2023); KCCB links catholic-hierarchy.org only.",
    "KE-NRY-MSB": "Official site publishes 17 parishes but no deanery grouping.",
    "KE-NRY-EMB": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-NRY-NYH": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-NRY-MRL": "Official domain maralalcatholic.org no longer serves diocesan content.",
    "KE-NRY-ISL": "Official site publishes 15 parishes but no deanery breakdown.",
    "KE-KSM-KSM": "KCCB links catholic-hierarchy.org only; no official archdiocesan site with deanery list.",
    "KE-KSM-ELD": "Official site has a deaneries page but publishes no deanery names.",
    "KE-KSM-KSI": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-KSM-LOD": "Official site returns HTTP 403; no verifiable listing.",
    "KE-KSM-KAK": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-KSM-BUN": "KCCB links catholic-hierarchy.org only; no official diocesan site with deanery list.",
    "KE-KSM-HBY": "Official site is JavaScript-rendered; no static listing retrievable.",
    "KE-KSM-KAP": "Newly erected (2025); KCCB links catholic-hierarchy.org only.",
    "KE-MBA-GRS": "Official site has a parishes page but publishes no deanery grouping.",
    "KE-MBA-MLD": "Official site unreachable at time of import.",
}

# Dioceses with verified deaneries whose parish lists are still pending.
DIOCESES_WITH_DEANERIES_BUT_PENDING_PARISHES = (
    "KE-NRB-NGO",
    "KE-NRB-KTI",
    "KE-NRY-NYR",
    "KE-NRY-MER",
    "KE-NRY-MRG",
    "KE-MBA-MBA",
    "KE-KSM-KTL",
)


def coverage() -> dict:
    """Summarise what this data set does and does not cover."""
    dioceses_with_parishes = sorted({p["diocese_code"] for p in PARISHES})
    return {
        "countries": len(COUNTRIES),
        "provinces": len(PROVINCES),
        "dioceses": len(ALL_DIOCESES),
        "geographic_dioceses": len([d for d in ALL_DIOCESES if not d["is_military_ordinariate"]]),
        "military_ordinariates": len(
            [d for d in ALL_DIOCESES if d["is_military_ordinariate"]]
        ),
        "deaneries": len(DEANERIES),
        "parishes": len(PARISHES),
        "dioceses_with_parish_data": dioceses_with_parishes,
        "dioceses_without_official_deanery_data": sorted(
            DIOCESES_WITHOUT_OFFICIAL_DEANERY_DATA
        ),
        "dioceses_with_deaneries_but_pending_parishes": list(
            DIOCESES_WITH_DEANERIES_BUT_PENDING_PARISHES
        ),
    }


__all__ = [
    "ALL_DIOCESES",
    "COUNTRIES",
    "DEANERIES",
    "DIOCESES_WITH_DEANERIES_BUT_PENDING_PARISHES",
    "DIOCESES_WITHOUT_OFFICIAL_DEANERY_DATA",
    "INCOMPLETE",
    "KCCB_DIOCESES_URL",
    "MILITARY_ORDINARIATE",
    "NEEDS_REVIEW",
    "PARISHES",
    "PROVINCES",
    "VERIFIED",
    "VERIFIED_ON",
    "build_parishes",
    "coverage",
    "parish_code",
    "slugify",
]