"""Rule-based filter tags for transcripts. Edit the taxonomies below to add or refine tags.

Profile tags (background, optional, state, interests) are read from the DAF line and the header
block, so a question about Kerala doesn't make the candidate Keralite. Topic tags are read from the
questions (everything after the header).
"""

from __future__ import annotations

import re

from .transcripts import SECTION

# tag -> regex alternatives (case-insensitive, matched on word boundaries)
BACKGROUND = {
    "Engineering": r"b\.?\s?tech|b\.?e\b|m\.?tech|engineer\w*|engg|iit\b|iit\s?\w+|nit\b|nit\s?\w+|bits|ece|eee|cse\b|"
                   r"computer science|mechanical|civil engg|electrical|electronics|chemical engineering|aerospace",
    "Medical": r"mbbs|bds|bams|bhms|doctor|medical officer|aiims|md\b|ms ortho|dentist|dental|nursing|pharmacy",
    "Law": r"llb|ll\.b|llm|nlu|advocate|lawyer|\blaw\b|legal",
    "Commerce & Finance": r"b\.?com|commerce|chartered accountant|\bca\b|cfa|finance|banking|accountancy|audit",
    "Management": r"mba|iim\b|iim\s?\w+|management|consult\w+|marketing|business analyst",
    "Science": r"b\.?sc|m\.?sc|physics|chemistry|biology|zoology|botany|mathematics|maths|statistics|biotech\w*|phd",
    "Humanities": r"b\.a\b|\bba\b(?!')|m\.a\b|history|political science|english lit\w*|hindi lit\w*|economics|philosophy|"
                  r"psychology|jnu|du\b|delhi university|literature",
    "Agriculture & Veterinary": r"agricultur\w*|b\.?sc\.? agri|veterinary|bvsc|horticulture|forestry|fisheries",
    "Defence background": r"\bnda\b|army|navy|air force|capf|ssb|defence officer|military school|sainik",
}

OPTIONAL = {
    "PSIR": r"psir|political science(?: and| &) (?:ir|international relations)|pol\.? sc\w*",
    "Sociology": r"sociology|socio\b",
    "Anthropology": r"anthropology|anthro\b",
    "Geography": r"geography",
    "History": r"history",
    "Public Administration": r"public admin\w*|pub\.? ad\b",
    "Philosophy": r"philosophy",
    "Economics": r"economics",
    "Mathematics": r"mathematics|maths?\b",
    "Physics": r"physics",
    "Chemistry": r"chemistry",
    "Law": r"\blaw\b",
    "Medical Science": r"medical science",
    "Commerce & Accountancy": r"commerce(?: and| &) accountancy|commerce",
    "Management": r"management",
    "Agriculture": r"agriculture",
    "Psychology": r"psychology",
    "Geology": r"geology",
    "Civil Engineering": r"civil engineering",
    "Electrical Engineering": r"electrical engineering",
    "Mechanical Engineering": r"mechanical engineering",
    "Animal Husbandry & Vet. Science": r"animal husbandry|veterinary",
    "Zoology": r"zoology",
    "Botany": r"botany",
    "Statistics": r"statistics",
    "Hindi Literature": r"hindi lit\w*",
    "Malayalam Literature": r"malayalam lit\w*",
    "Tamil Literature": r"tamil lit\w*",
    "Telugu Literature": r"telugu lit\w*",
    "Kannada Literature": r"kannada lit\w*",
    "Marathi Literature": r"marathi lit\w*",
    "Sanskrit Literature": r"sanskrit",
    "Urdu Literature": r"urdu lit\w*",
    "English Literature": r"english lit\w*",
}
# Optional subjects named bare in a DAF list ("PSIR, Kerala, cricket") are only trusted for these.
OPTIONAL_UNAMBIGUOUS = {"PSIR", "Sociology", "Anthropology", "Public Administration"}

STATES = {
    "Andhra Pradesh": r"andhra|vijayawada|visakhapatnam|vizag|guntur|tirupati",
    "Assam": r"assam|guwahati",
    "Bihar": r"bihar|patna|muzaffarpur|gaya|darbhanga|bhagalpur",
    "Chhattisgarh": r"chhattisgarh|raipur|bilaspur",
    "Delhi": r"delhi",
    "Goa": r"\bgoa\b",
    "Gujarat": r"gujarat|ahmedabad|surat|vadodara|rajkot",
    "Haryana": r"haryana|gurgaon|gurugram|rohtak|hisar|panipat|rewari",
    "Himachal Pradesh": r"himachal|shimla|\bhp\b",
    "Jammu & Kashmir": r"kashmir|jammu|srinagar|ladakh",
    "Jharkhand": r"jharkhand|ranchi|dhanbad|jamshedpur|bokaro",
    "Karnataka": r"karnataka|bengaluru|bangalore|mysore|mysuru|mangalore",
    "Kerala": r"kerala|thiruvananthapuram|trivandrum|kochi|kozhikode|thrissur|malappuram",
    "Madhya Pradesh": r"madhya pradesh|\bmp\b|bhopal|indore|jabalpur|gwalior|vidisha",
    "Maharashtra": r"maharashtra|mumbai|pune|nagpur|nashik|aurangabad|satara|latur|jalgaon",
    "North East": r"manipur|meghalaya|mizoram|nagaland|tripura|arunachal|sikkim|shillong",
    "Odisha": r"odisha|orissa|bhubaneswar|cuttack",
    "Punjab": r"punjab|ludhiana|amritsar|chandigarh",
    "Rajasthan": r"rajasthan|jaipur|kota|jodhpur|udaipur|bikaner|jaisalmer|ajmer|jhunjhunu|sikar|alwar",
    "Tamil Nadu": r"tamil\s?nadu|chennai|coimbatore|madurai|\btn\b",
    "Telangana": r"telangana|hyderabad|warangal",
    "Uttar Pradesh": r"uttar pradesh|\bup\b|lucknow|kanpur|varanasi|prayagraj|allahabad|meerut|agra|gorakhpur|"
                     r"bareilly|noida|ghaziabad|aligarh|bulandshahr|sultanpur|amroha|shahjahanpur|rampur",
    "Uttarakhand": r"uttara?k?hand|dehradun|haridwar|nainital|garhwal|kumaon",
    "West Bengal": r"west bengal|kolkata|calcutta|darjeeling",
}

INTERESTS = {
    "Cricket": r"cricket",
    "Football": r"football",
    "Chess": r"chess",
    "Badminton & racquet sports": r"badminton|tennis|squash|table tennis",
    "Other sports": r"volleyball|basketball|kabaddi|hockey|athletics|swimming|karate|boxing|kho\s?kho|shooting",
    "Fitness & running": r"running|marathon|gym|strength training|jogging|cycling|fitness",
    "Yoga & meditation": r"yoga|meditation|vipassana|mindfulness|sudarshan kriya",
    "Cooking": r"cooking|baking|culinary|cuisine",
    "Music": r"music|singing|songs|guitar|flute|tabla|ghazal\w*",
    "Poetry & writing": r"poetry|poems?|writing|blog\w*|journaling|shayari",
    "Reading": r"reading|books|novels|fiction",
    "Movies & series": r"movies|films?|cinema|web series|sitcoms",
    "Art & craft": r"painting|sketch\w*|drawing|art\b|craft|photography",
    "Travel & trekking": r"travel\w*|trek\w*|hiking|mountaineering",
    "NCC / NSS / volunteering": r"\bncc\b|\bnss\b|volunteer\w*|\bngo\b|blood donation|social work|teach for india",
    "Gardening & nature": r"gardening|bird\s?watching|nature|stargazing",
    "Finance & markets": r"stock market|investing|trading|personal finance",
}

TOPICS = {
    "International Relations": r"china|pakistan|bangladesh|nepal|bhutan|sri\s?lanka|maldives|myanmar|afghanistan|"
                               r"usa|america|trump|russia|ukraine|israel|gaza|iran|west asia|middle east|"
                               r"foreign policy|diplomac\w*|unsc|united nations|\bun\b|brics|quad|g20|sco|asean|"
                               r"neighbourhood|bilateral|geopolitic\w*",
    "Polity & Constitution": r"constitution\w*|article \d+|fundamental rights?|parliament|governor|judiciary|"
                             r"supreme court|high court|federalism|election\w*|collegium|amendment|basic structure|"
                             r"panchayat|delimitation|president|legislat\w*|ordinance|preamble",
    "Governance & Administration": r"district magistrate|\bdm\b|collector|bureaucra\w*|civil servant\w*|administrat\w*|"
                                   r"corruption|\brti\b|governance|e-governance|lateral entry|ias officer|"
                                   r"implementation|scheme",
    "Economy": r"gdp|inflation|\brbi\b|repo|budget|tax\w*|gst|fiscal|tariff\w*|economy|economic|banking|"
               r"unemployment|msme|startup\w*|manufacturing|fdi|trade deal|freebies|subsid\w*|disinvestment",
    "Agriculture & Rural": r"farmer\w*|\bmsp\b|agricultur\w*|crop\w*|irrigation|paddy|kisan|rural|village\w*|"
                           r"cooperative\w*|dairy",
    "Environment & Disasters": r"climate|pollution|environment\w*|forest\w*|wildlife|biodiversity|renewable|solar|"
                               r"carbon|\bcop\s?\d*|flood\w*|drought|disaster\w*|cyclone|earthquake|green hydrogen",
    "Science & Technology": r"\bai\b|artificial intelligence|semiconductor\w*|isro|space|quantum|technolog\w*|"
                            r"cyber|blockchain|digital|data protection|chatgpt|robot\w*|5g|biotech\w*",
    "Security & Defence": r"army|defence|defense|naxal\w*|terroris\w*|border|military|operation sindoor|op sindoor|"
                          r"insurgen\w*|internal security|nuclear|police|agniveer|missile|war",
    "Society & Social Justice": r"women|gender|caste|reservation|tribal|poverty|inequalit\w*|population|ageing|elderly|"
                                r"migration|communal|dowry|child\w*|disabilit\w*|lgbt\w*|marginali\w*",
    "Education": r"education|school\w*|universit\w*|\bnep\b|coaching|teacher\w*|learning outcome\w*|students?",
    "Health": r"health\w*|hospital\w*|disease\w*|ayushman|nutrition|malnutrition|mental health|suicide|drug\w*|"
              r"addiction|pandemic|covid",
    "History & Culture": r"histor\w*|freedom struggle|gandhi\w*|nehru|ambedkar|mughal\w*|ancient|medieval|temple\w*|"
                         r"heritage|culture|cultural|festival\w*|kumbh|dance|monument\w*|dynasty|british",
    "Ethics & Values": r"ethic\w*|integrity|honest\w*|values?|moral\w*|dilemma|conscience|empathy",
    "Geography": r"river\w*|mountain\w*|monsoon|plateau|latitude|longitude|tropic of|ghats|himalaya\w*|"
                 r"soil|mineral\w*|coastline",
    "Sports": r"cricket|olympic\w*|sports?|football|chess|badminton|hockey|athlete\w*|world cup",
    "Situational / Hypothetical": r"suppose you|what will you do|what would you do|if you are (?:a|the) \w+|"
                                  r"as (?:a |the )?(?:dm|sp|collector|cs|chief secretary|secretary)\b|"
                                  r"your senior (?:asks|tells)",
    "Motivation & Personal": r"why civil services|why upsc|why ias|service preference|strengths?|weakness\w*|"
                             r"introduce yourself|role model|plan b|first attempt|last attempt|why do you want",
}


def _compile(tax: dict[str, str]) -> list[tuple[str, re.Pattern]]:
    return [(tag, re.compile(rf"(?<![\w.])(?:{rx})(?!\w)", re.I)) for tag, rx in tax.items()]


_BACKGROUND, _OPTIONAL, _STATES, _INTERESTS, _TOPICS = map(_compile, (BACKGROUND, OPTIONAL, STATES, INTERESTS, TOPICS))
_OPTIONAL_PHRASE = re.compile(r"(?i)([a-z][a-z &()]{2,45}?)\s+(?:optional|opt)\b|opt(?:ional)?\s*[:\-–]\s*([^\n,;]{2,50})")


# Topics distinctive enough that a single mention counts; the rest need TOPIC_MIN_HITS.
SINGLE_HIT_TOPICS = {"Situational / Hypothetical", "Motivation & Personal"}
TOPIC_MIN_HITS = 2


def _match(compiled: list[tuple[str, re.Pattern]], text: str) -> list[str]:
    return [tag for tag, rx in compiled if rx.search(text)]


def match_topics(text: str) -> list[str]:
    """Topics mentioned at all in a short text (one question, one headline)."""
    return [tag for tag, rx in _TOPICS if rx.search(text)]


def topic_tags(text: str) -> list[str]:
    q = question_text(text)
    return [tag for tag, rx in _TOPICS
            if len(rx.findall(q)) >= (1 if tag in SINGLE_HIT_TOPICS else TOPIC_MIN_HITS)]


def header_block(text: str) -> str:
    """Lines before the first member section (Chairman / M1 / ...), capped."""
    m = SECTION.search(text)
    return text[: m.start() if m and m.start() < 1500 else 900]


def question_text(text: str) -> str:
    m = SECTION.search(text)
    return text[m.start():] if m else text[600:]


def optional_tag(optional_field: str | None, daf: str | None, header: str) -> str | None:
    candidates = [optional_field or ""] + [g1 or g2 for g1, g2 in _OPTIONAL_PHRASE.findall(header)]
    for c in candidates:
        found = _match(_OPTIONAL, c)
        if found:
            return found[0]
    bare = [t for t in _match(_OPTIONAL, daf or "") if t in OPTIONAL_UNAMBIGUOUS]
    return bare[0] if len(bare) == 1 else None


def profile_tags(text: str) -> dict:
    """Background, state, interests and optional read from free text such as a candidate's DAF."""
    return {"background": _match(_BACKGROUND, text), "states": _match(_STATES, text),
            "interests": _match(_INTERESTS, text), "optional_tag": optional_tag(None, text, text)}


def tag_transcript(text: str, daf: str | None, optional_field: str | None) -> dict:
    header = header_block(text)
    profile = f"{daf or ''}\n{header}"
    return {
        "background": _match(_BACKGROUND, profile),
        "optional_tag": optional_tag(optional_field, daf, header),
        "states": _match(_STATES, profile),
        "interests": _match(_INTERESTS, daf or header),
        "topics": topic_tags(text),
    }
