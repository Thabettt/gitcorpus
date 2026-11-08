"""Conservative GitHub profile location-to-country resolution.

Signals are combined only when they agree. Ambiguous profiles remain unmatched
because owner-country filters are research selection criteria, where a false
positive is more damaging than an honest unknown.
"""

from __future__ import annotations

import math
import re
import threading
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

import geonamescache
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from lib.batching import chunked
from store.models import GeoCache as GeoCacheRow

_FLAG_PATTERN = re.compile("[\U0001f1e6-\U0001f1ff]{2}")
_REGIONAL_INDICATORS = frozenset(range(0x1F1E6, 0x1F1FF + 1))
_TAG_FLAG = re.compile("\U0001f3f4([\U000e0020-\U000e007e]+)\U000e007f")
_TAG_OFFSET = 0xE0000
_TAG_FLAGS = {"gbeng": "GB", "gbsct": "GB", "gbwls": "GB", "gbnir": "GB"}
_CANDIDATE_SPLIT = re.compile(r"(?:\s+[–—-]\s+|[/|,•;:()\[\]{}\n\r]+)")
_PHRASE_SPLIT = re.compile(
    r"\b(?:based\s+in|living\s+in|located\s+in|working\s+in|remote\s+in|from)\b",
    re.IGNORECASE,
)
_DOTTED_ACRONYM = re.compile(r"\b(?:[A-Za-z]\.){2,}")
_CONTACT_LIKE = re.compile(
    r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://\S+|www\.\S+|^[\w-]+\.[A-Za-z]{2,}$)",
    re.IGNORECASE,
)
_SKIPPED_MARKS = frozenset({"\ufe0e", "\ufe0f"})
_FOLD_CHARS = str.maketrans(
    {
        "ø": "o",
        "æ": "ae",
        "å": "a",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "þ": "th",
        "ı": "i",
        "ß": "ss",
        "œ": "oe",
    }
)

# Changing matching semantics must change this value. Cache rows and owner
# enrichment are versioned so a resolver upgrade can never silently reuse an
# answer produced by older rules.
GEO_RESOLVER_VERSION = "2026-11-precision-v1"
_MAX_LOCATION_CHARS = 512

_COUNTRY_ALIASES_RAW = """\
AD andorra|andorran
AE united arab emirates|uae|emirates|emirati
AF afghanistan|afghan
AG antigua and barbuda|antiguan
AI anguilla
AL albania|albanian
AM armenia|armenian
AO angola|angolan
AQ antarctica
AR argentina|argentine|argentinian
AS american samoa
AT austria|austrian|osterreich|österreich
AU australia|australian|aussie
AW aruba
AX aland islands|aland
AZ azerbaijan|azerbaijani
BA bosnia and herzegovina|bosnia|bosnian
BB barbados|barbadian
BD bangladesh|bangladeshi
BE belgium|belgian|belgie|belgië
BF burkina faso|burkinabe
BG bulgaria|bulgarian
BH bahrain|bahraini
BI burundi|burundian
BJ benin|beninese
BL saint barthelemy
BM bermuda
BN brunei
BO bolivia|bolivian
BQ caribbean netherlands
BR brazil|brasil|brazilian
BS bahamas|bahamian
BT bhutan|bhutanese
BV bouvet island
BW botswana|batswana
BY belarus|belarusian
BZ belize|belizean
CA canada|canadian
CC cocos islands
CD democratic republic of the congo|dr congo|congo kinshasa
CF central african republic
CG republic of the congo|congo brazzaville
CH switzerland|swiss|schweiz|suisse|svizzera
CI cote d ivoire|ivory coast|ivorian
CK cook islands
CL chile|chilean
CM cameroon|cameroonian
CN china|chinese|prc
CO colombia|colombian
CR costa rica|rican
CU cuba|cuban
CV cape verde
CW curacao
CX christmas island
CY cyprus|cypriot
CZ czechia|czech republic|czech
DE germany|deutschland|german
DJ djibouti
DK denmark|danish|danmark
DM dominica
DO dominican republic|dominican
DZ algeria|algerian
EC ecuador|ecuadorian
EE estonia|estonian
EG egypt|egyptian
EH western sahara
ER eritrea|eritrean
ES spain|spanish|espana|españa
ET ethiopia|ethiopian
FI finland|finnish|suomi
FJ fiji|fijian
FK falkland islands
FM micronesia|micronesian
FO faroe islands
FR france|french
GA gabon|gabonese
GB united kingdom|uk|great britain|britain
GB england|scotland|wales|northern ireland
GB british|english|scottish|welsh
GD grenada|grenadian
GE georgia|georgian
GF french guiana
GG guernsey
GH ghana|ghanaian
GI gibraltar
GL greenland
GM gambia|gambian
GN guinea|guinean
GP guadeloupe
GQ equatorial guinea
GR greece|greek|hellas
GS south georgia
GT guatemala|guatemalan
GU guam
GW guinea bissau
GY guyana|guyanese
HK hong kong|hongkonger
HM heard island
HN honduras|honduran
HR croatia|croatian|hrvatska
HT haiti|haitian
HU hungary|hungarian|magyarorszag
ID indonesia|indonesian
IE ireland|irish|eire
IL israel|israeli
IM isle of man
IN india|indian
IO british indian ocean territory
IQ iraq|iraqi
IR iran|iranian|persia
IS iceland|icelandic
IT italy|italian|italia
JE jersey
JM jamaica|jamaican
JO jordan|jordanian
JP japan|japanese|nippon
KE kenya|kenyan
KG kyrgyzstan|kyrgyz
KH cambodia|cambodian
KI kiribati
KM comoros|comorian
KN saint kitts and nevis
KP north korea|dprk
KR south korea|korea|republic of korea
KW kuwait|kuwaiti
KY cayman islands
KZ kazakhstan|kazakh
LA laos|lao
LB lebanon|lebanese
LC saint lucia
LI liechtenstein
LK sri lanka|sri lankan
LR liberia|liberian
LS lesotho|basotho
LT lithuania|lithuanian
LU luxembourg|luxembourgish
LV latvia|latvian
LY libya|libyan
MA morocco|moroccan
MC monaco|monegasque
MD moldova|moldovan
ME montenegro|montenegrin
MF saint martin
MG madagascar|malagasy
MH marshall islands
MK north macedonia|macedonia|macedonian
ML mali|malian
MM myanmar|burma|burmese
MN mongolia|mongolian
MO macao|macau
MP northern mariana islands
MQ martinique
MR mauritania|mauritanian
MS montserrat
MT malta|maltese
MU mauritius|mauritian
MV maldives|maldivian
MW malawi|malawian
MX mexico|mexican|méxico
MY malaysia|malaysian
MZ mozambique|mozambican
NA namibia|namibian
NC new caledonia
NE niger|nigerien
NF norfolk island
NG nigeria|nigerian
NI nicaragua|nicaraguan
NL netherlands|nederland|holland|dutch
NO norway|norwegian|norge
NP nepal|nepali|nepalese
NR nauru|nauruan
NU niue
NZ new zealand|new zealander|kiwi|aotearoa
OM oman|omani
PA panama|panamanian
PE peru|peruvian|perú
PF french polynesia
PG papua new guinea
PH philippines|filipino|pinoy
PK pakistan|pakistani
PL poland|polish|polska
PM saint pierre and miquelon
PN pitcairn
PR puerto rico|puerto rican
PS palestine|palestinian
PT portugal|portuguese
PW palau|palauan
PY paraguay|paraguayan
QA qatar|qatari
RE reunion|réunion
RO romania|romanian
RS serbia|serbian
RU russia|russian|rossiya
RW rwanda|rwandan
SA saudi arabia|saudi|ksa
SB solomon islands
SC seychelles|seychellois
SD sudan|sudanese
SE sweden|swedish|sverige
SG singapore|singaporean
SH saint helena
SI slovenia|slovenian
SJ svalbard
SK slovakia|slovak
SL sierra leone|sierra leonean
SM san marino
SN senegal|senegalese
SO somalia|somali
SR suriname|surinamese
SS south sudan
ST sao tome and principe
SV el salvador|salvadoran
SX sint maarten
SY syria|syrian
SZ eswatini|swaziland|swazi
TC turks and caicos islands
TD chad|chadian
TF french southern territories
TG togo|togolese
TH thailand|thai
TJ tajikistan|tajik
TK tokelau
TL timor leste|east timor
TM turkmenistan|turkmen
TN tunisia|tunisian
TO tonga|tongan
TR turkey|turkish|turkiye|türkiye
TT trinidad and tobago|trinidadian
TV tuvalu
TW taiwan|taiwanese
TZ tanzania|tanzanian
UA ukraine|ukrainian
UG uganda|ugandan
UM united states minor outlying islands
US united states|usa|america|united states of america
US american
UY uruguay|uruguayan
UZ uzbekistan|uzbek
VA vatican city|holy see
VC saint vincent and the grenadines
VE venezuela|venezuelan
VG british virgin islands
VI united states virgin islands|us virgin islands
VN vietnam|vietnamese
VU vanuatu
WF wallis and futuna
WS samoa|samoan
YE yemen|yemeni
YT mayotte
ZA south africa|south african
ZM zambia|zambian
ZW zimbabwe|zimbabwean
"""

_GAZETTEER_RAW = """\
AE dubai|abu dhabi|sharjah|al ain|ajman|ras al khaimah
AF kabul
AO luanda
AR buenos aires|cordoba|córdoba|rosario|mendoza|la plata
AR tucuman|tucumán|mar del plata|salta|santa fe
AT vienna|wien|graz|linz|salzburg|innsbruck
AU sydney|melbourne|brisbane|perth|adelaide|gold coast
AU canberra|wollongong|geelong|hobart|darwin|cairns|toowoomba
AZ baku
BD dhaka|chittagong|chattogram|khulna|rajshahi|sylhet
BE brussels|bruxelles|antwerp|antwerpen|ghent|gent
BE charleroi|liege|liège|bruges|brugge
BF ouagadougou
BG sofia|plovdiv|varna|burgas|ruse
BH manama
BO la paz|santa cruz|cochabamba
BR sao paulo|são paulo|rio de janeiro|brasilia|brasília
BR salvador|fortaleza|belo horizonte|manaus|curitiba|recife
BR porto alegre|belem|belém|goiania|goiânia|guarulhos
BR campinas|sao luis|maceio|natal|joao pessoa|teresina
BR cuiaba|campo grande|florianopolis|vitoria
BY minsk
CA toronto|montreal|vancouver|calgary|edmonton|ottawa
CA winnipeg|quebec city|quebec|hamilton|kitchener|mississauga
CA windsor|victoria|halifax|regina|saskatoon
CH zurich|zürich|geneva|geneve|genève|basel
CH bern|berne|lausanne|lucerne
CI abidjan|yamoussoukro
CL santiago|valparaiso|valparaíso|concepcion|concepción
CL la serena|antofagasta|temuco
CM douala|yaounde
CN beijing|shanghai|guangzhou|shenzhen|chengdu|chongqing
CN wuhan|xi'an|xian|hangzhou|nanjing|tianjin
CN suzhou|dongguan|qingdao|zhengzhou|changsha|kunming
CN dalian|xiamen|hefei|fuzhou|harbin|jinan
CN nanning|taiyuan|shijiazhuang|urumqi|lanzhou|foshan
CO bogota|bogotá|medellin|medellín|cali
CO barranquilla|cartagena|bucaramanga|cucuta
CR san jose costa rica
CU havana|habana
CZ prague|praha|brno|ostrava|plzen|plzeň|liberec
DE berlin|munich|munchen|münchen|hamburg|frankfurt
DE cologne|koln|köln|stuttgart|dusseldorf|düsseldorf
DE dortmund|essen|leipzig|dresden|hanover|hannover
DE nuremberg|nürnberg|bremen|bonn|mannheim|karlsruhe
DE munster|münster
DK copenhagen|kobenhavn|københavn|aarhus|odense|aalborg|esbjerg
DO santo domingo
DZ algiers|oran|constantine
EC quito|guayaquil|cuenca
EE tallinn|tartu
EG cairo|alexandria|giza|luxor|aswan
ES madrid|barcelona|valencia|seville|sevilla|zaragoza
ES malaga|málaga|murcia|palma|bilbao|alicante
ES valladolid|vigo|gijon|gijón|granada|oviedo
ES la coruna|a coruna|santa cruz de tenerife
ET addis ababa|dire dawa
FI helsinki|espoo|tampere|vantaa|oulu|turku|jvaskyla
FR paris|marseille|lyon|toulouse|nice|nantes
FR montpellier|strasbourg|bordeaux|lille|rennes|reims
FR toulon|grenoble|dijon|angers|nimes|nîmes
FR villeurbanne|saint-etienne|saint etienne
GB london|birmingham|manchester|glasgow|liverpool|leeds
GB sheffield|edinburgh|bristol|cardiff|belfast|newcastle
GB nottingham|leicester|southampton|portsmouth|brighton
GB aberdeen|cambridge|oxford|york|reading|swansea|plymouth|coventry
GE tbilisi|batumi
GH accra|kumasi|tamale
GR athens|athina|thessaloniki|patras|heraklion|larissa
GT guatemala city
HK hong kong
HR zagreb|split|rijeka|osijek
HU budapest|debrecen|szeged|miskolc|pecs|pécs
ID jakarta|surabaya|bandung|medan|semarang|makassar
ID palembang|tangerang|depok|bekasi|denpasar
IE dublin|cork|limerick|galway|waterford
IL tel aviv|jerusalem|haifa|beersheba|netanya
IN mumbai|bombay|delhi|new delhi|bangalore|bengaluru
IN hyderabad|chennai|madras|kolkata|calcutta|pune
IN ahmedabad|surat|jaipur|lucknow|kanpur|nagpur|indore
IN thane|bhopal|visakhapatnam|patna|vadodara|ludhiana|agra
IN nashik|faridabad|meerut|rajkot|varanasi|srinagar
IN aurangabad|amritsar|allahabad|prayagraj|ranchi|howrah
IN coimbatore|jabalpur|gwalior|vijayawada|jodhpur|madurai
IN raipur|guwahati|chandigarh|mysore|mysuru|bareilly
IN aligarh|tiruppur|moradabad|jalandhar|bhubaneswar|salem
IN warangal|guntur|bhiwandi|saharanpur|gorakhpur|bikaner
IN amravati|noida|jamshedpur|bhilai|cuttack|firozabad
IN kochi|cochin|nellore|bhavnagar|dehradun|durgapur
IN asansol|rourkela|nanded|kolhapur|ajmer|akola
IN gulbarga|jamnagar|ujjain|loni|siliguri|jhansi
IN ulhasnagar|jammu|sangli|mangalore|erode|belgaum
IN ambattur|tirunelveli|malegaon|gaya|jalgaon|udaipur
IN davanagere|kozhikode|calicut|kurnool|rajahmundry|bokaro
IN bellary|patiala|agartala|bhagalpur|latur|dhule|rohtak
IQ baghdad|basra|mosul|erbil
IR tehran|mashhad|isfahan|shiraz|tabriz|qom|ahvaz
IS reykjavik
IT rome|roma|milan|milano|naples|napoli|turin|torino
IT palermo|genoa|genova|bologna|florence|firenze|bari
IT catania|venice|venezia|verona|messina|padua|padova
IT trieste|brescia|parma|cagliari
JM kingston
JO amman
JP tokyo|osaka|yokohama|nagoya|sapporo|fukuoka
JP kobe|kyoto|kawasaki|saitama|hiroshima|sendai
JP chiba|kitakyushu|sakai
KE nairobi|mombasa|kisumu|nakuru
KG bishkek
KH phnom penh
KR seoul|busan|incheon|daegu|daejeon|gwangju|suwon|ulsan|changwon
KW kuwait city
KZ almaty|astana|nur-sultan
LB beirut
LK colombo|kandy
LT vilnius|kaunas
LV riga
LY tripoli|benghazi
MA casablanca|rabat|marrakesh|fes|tangier
MD chisinau
MM yangon|mandalay
MU port louis
MX mexico city|guadalajara|monterrey|puebla|tijuana|leon
MX juarez|ciudad juarez|zapopan|merida|mérida|cancun
MX toluca|queretaro|querétaro
MY kuala lumpur|george town|johor bahru|ipoh
MY shah alam|petaling jaya|kuching|kota kinabalu
MZ maputo
NG lagos|abuja|kano|ibadan|port harcourt|benin city|kaduna|enugu
NL amsterdam|rotterdam|the hague|den haag|utrecht|eindhoven
NL groningen|tilburg|almere|breda|nijmegen|haarlem
NO oslo|bergen|trondheim|stavanger|drammen|fredrikstad
NP kathmandu|pokhara
NZ auckland|wellington|christchurch|tauranga|dunedin
OM muscat
PA panama city
PE lima|arequipa|trujillo|chiclayo|cusco|piura
PH manila|quezon city|davao|cagayan de oro|cebu|zamboanga|makati
PK karachi|lahore|faisalabad|rawalpindi|islamabad|multan
PK gujranwala|peshawar|quetta
PL warsaw|warszawa|krakow|kraków|lodz|łódź|wroclaw|wrocław
PL poznan|poznań|gdansk|gdańsk|szczecin|bydgoszcz
PL lublin|katowice|bialystok
PT lisbon|lisboa|porto|braga|coimbra|faro|funchal
PY asuncion
QA doha
RO bucharest|bucuresti|cluj-napoca|cluj napoca|timisoara
RO timișoara|iasi|iași|constanta|constanța|brasov|brașov|craiova
RS belgrade|novi sad|nis|niš|kragujevac
RU moscow|moskva|saint petersburg|st petersburg|novosibirsk
RU yekaterinburg|kazan|nizhny novgorod|chelyabinsk|samara
RU omsk|rostov-on-don|rostov on don|ufa|krasnoyarsk
RU voronezh|perm|volgograd
RW kigali
SA riyadh|jeddah|mecca|medina|dammam|khobar|tabuk
SE stockholm|gothenburg|goteborg|göteborg|malmo|malmö
SE uppsala|vasteras|västerås|orebro|örebro
SE linkoping|linköping|helsingborg
SG singapore
SI ljubljana|maribor
SK bratislava|kosice|košice|presov|prešov
SN dakar
TH bangkok|chiang mai|pattaya|phuket|khon kaen|hat yai
TN tunis
TR istanbul|ankara|izmir|bursa|antalya|adana|gaziantep
TR konya|kayseri
TT port of spain
TW taipei|kaohsiung|taichung|tainan
TZ dar es salaam|dodoma|arusha|mwanza
UA kyiv|kiev|kharkiv|odesa|odessa|dnipro|donetsk|lviv
UG kampala
US new york|new york city|los angeles|chicago|houston|phoenix
US philadelphia|san antonio|san diego|dallas|san jose|austin
US jacksonville|fort worth|columbus|charlotte|indianapolis
US san francisco|seattle|denver|washington|boston|el paso
US nashville|detroit|oklahoma city|portland|las vegas|memphis
US louisville|baltimore|milwaukee|albuquerque|tucson|fresno
US sacramento|kansas city|atlanta|omaha|raleigh|miami
US minneapolis|tampa|new orleans|cleveland|honolulu
US pittsburgh|st louis|saint louis|cincinnati|orlando|buffalo
US salt lake city|boise|richmond|spokane|des moines|rochester
UY montevideo
UZ tashkent|samarkand
VE caracas|maracaibo|barquisimeto|maracay
VN ho chi minh city|ho chi minh|saigon|hanoi|haiphong|ha noi
VN da nang|danang|can tho|bien hoa|hue
ZA johannesburg|cape town|durban|pretoria
ZA port elizabeth|bloemfontein|soweto
ZM lusaka
ZW harare|bulawayo
"""

# Formal names, common abbreviations and spellings that appear in GitHub
# profiles but are absent from the compact canonical table above. Location
# shorthands such as NYC/SF deliberately live in the city table, not here: a
# city must never receive country-name confidence.
_EXTRA_COUNTRY_ALIASES_RAW = """\
AE u a e|the emirates
BR brazil federative republic
CD drc|d r c|democratic republic of congo|the democratic republic of the congo
CG congo brazzaville|the republic of the congo
CV cabo verde
CZ the czech republic
DE federal republic of germany
GB u k|united kingdom of great britain and northern ireland
HK hong kong sar
IR islamic republic of iran
KP d p r k
KR republic of korea
KR korea republic of|korea south
LA lao pdr
MM burma
MO macao sar|macau sar
NL the netherlands
RU russian federation
SY syrian arab republic
TL east timor
TR turkiye
US us|u s|the us|the united states
VG virgin islands british
VI virgin islands us|virgin islands u s
VN viet nam
"""

# Country names in their own scripts. Cities are intentionally separate so
# Москва is city evidence, not the stronger country-name evidence.
_SCRIPT_COUNTRY_ALIASES: dict[str, str] = {
    "中国": "CN",
    "中华人民共和国": "CN",
    "中国大陆": "CN",
    "日本": "JP",
    "日本国": "JP",
    "한국": "KR",
    "대한민국": "KR",
    "台灣": "TW",
    "台湾": "TW",
    "香港": "HK",
    "澳門": "MO",
    "澳门": "MO",
    "新加坡": "SG",
    "马来西亚": "MY",
    "馬來西亞": "MY",
    "ประเทศไทย": "TH",
    "ไทย": "TH",
    "việt nam": "VN",
    "россия": "RU",
    "российская федерация": "RU",
    "україна": "UA",
    "украина": "UA",
    "беларусь": "BY",
    "қазақстан": "KZ",
    "ελλάδα": "GR",
    "ελλαδα": "GR",
    "مصر": "EG",
    "السعودية": "SA",
    "المملكة العربية السعودية": "SA",
    "الإمارات": "AE",
    "إسرائيل": "IL",
    "ישראל": "IL",
    "الهند": "IN",
    "भारत": "IN",
    "বাংলাদেশ": "BD",
    "پاکستان": "PK",
    "ایران": "IR",
    "تونس": "TN",
    "الجزائر": "DZ",
    "المغرب": "MA",
    "قطر": "QA",
    "الكويت": "KW",
    "عُمان": "OM",
    "البحرين": "BH",
    "الأردن": "JO",
    "لبنان": "LB",
    "سوريا": "SY",
    "العراق": "IQ",
    "فلسطين": "PS",
    "اليمن": "YE",
    "السودان": "SD",
    "ኢትዮጵያ": "ET",
    "ኤርትራ": "ER",
}

_SCRIPT_CITY_ALIASES: dict[str, str] = {
    "北京": "CN",
    "上海": "CN",
    "广州": "CN",
    "深圳": "CN",
    "东京": "JP",
    "大阪": "JP",
    "首尔": "KR",
    "서울": "KR",
    "台北": "TW",
    "曼谷": "TH",
    "孟买": "IN",
    "德里": "IN",
    "莫斯科": "RU",
    "圣彼得堡": "RU",
    "开罗": "EG",
    "柏林": "DE",
    "巴黎": "FR",
    "伦敦": "GB",
    "纽约": "US",
    "旧金山": "US",
    "洛杉矶": "US",
    "悉尼": "AU",
    "多伦多": "CA",
    "القاهرة": "EG",
    "الإسكندرية": "EG",
    "الرياض": "SA",
    "جدة": "SA",
    "دبي": "AE",
    "أبوظبي": "AE",
    "أبو ظبي": "AE",
    "الدار البيضاء": "MA",
    "الرباط": "MA",
    "طرابلس": "LY",
    "بيروت": "LB",
    "دمشق": "SY",
    "بغداد": "IQ",
    "عمّان": "JO",
    "القدس": "PS",
    "غزة": "PS",
    "صنعاء": "YE",
    "الخرطوم": "SD",
    "الدوحة": "QA",
    "مسقط": "OM",
    "المنامة": "BH",
    "إسطنبول": "TR",
    "أنقرة": "TR",
    "طهران": "IR",
    "كراتشي": "PK",
    "لاهور": "PK",
    "دلهي": "IN",
    "مومباي": "IN",
    "תל אביב": "IL",
    "ירושלים": "IL",
    "חיפה": "IL",
    "москва": "RU",
    "санкт петербург": "RU",
    "киев": "UA",
    "минск": "BY",
    "алматы": "KZ",
    "ташкент": "UZ",
    "бишкек": "KG",
    "тбилиси": "GE",
    "ереван": "AM",
    "баку": "AZ",
    "астана": "KZ",
}

# High-value location shorthand and cities seen in real GitHub profiles. The
# resolver stores every country for colliding names and refuses a bare
# ambiguous city unless another signal disambiguates it.
_EXTRA_CITIES_RAW = """\
AL tirana
AM yerevan
BA sarajevo
BW gaborone
BR blumenau|feira de santana|palhoca|palhoça|uberlandia|uberlândia
CA yellowknife|whitehorse|iqaluit|fredericton|charlottetown|nanaimo|kamloops
CD kinshasa
CF bangui
CG brazzaville
CR san jose
CY nicosia
ER asmara
FJ suva
FR aix en provence|annecy|avignon|poitiers|limoges|rouen|caen|nancy|metz|orleans|perpignan|pau|tours
GA libreville
GB huddersfield
GN conakry
HN tegucigalpa
HT port au prince
ID bali|yogyakarta
IT la spezia|modena|piacenza|pisa|lucca|trento
JP nara
KP pyongyang
KR seongnam|hanam|jeju island
LA vientiane
LR monrovia
LS maseru
ME podgorica
MG antananarivo
MN ulaanbaatar
MR nouakchott
MT valletta
MW lilongwe
NA windhoek
NI managua
PG port moresby
PH tawi tawi
SO mogadishu
SR paramaribo
SS juba
SY damascus
TJ dushanbe
TL dili
TM ashgabat
DK soro|sorø
US nyc|sf|bay area|silicon valley|jersey city|berkeley|arlington|albany|ann arbor
US brooklyn|manhattan|palo alto|mountain view|sunnyvale|pasadena|redwood city
US san mateo|santa clara|irvine|fremont|anchorage|ithaca|springfield|greater boston
US greater seattle area|north wales|johns island
YE sanaa
"""

_TZ_BANDS: dict[float, frozenset[str]] = {
    -10.0: frozenset({"US", "PF", "CK"}),
    -9.0: frozenset({"US", "PF"}),
    -8.0: frozenset({"US", "CA", "MX"}),
    -5.0: frozenset({"US", "CA", "CO", "PE", "EC", "CU"}),
    -3.0: frozenset({"BR", "AR", "UY"}),
    0.0: frozenset({"GB", "IE", "PT", "IS", "GH", "SN", "CI"}),
    1.0: frozenset({"DE", "FR", "IT", "ES", "NL", "BE", "AT", "PL", "CH", "NG"}),
    2.0: frozenset({"ZA", "EG", "GR", "FI", "RO", "IL", "UA"}),
    3.0: frozenset({"RU", "SA", "TR", "KE", "ET", "QA"}),
    3.5: frozenset({"IR"}),
    4.5: frozenset({"AF"}),
    5.5: frozenset({"IN", "LK"}),
    5.75: frozenset({"NP"}),
    6.5: frozenset({"MM", "CC"}),
    8.0: frozenset({"CN", "SG", "MY", "PH", "TW", "HK", "AU"}),
    9.0: frozenset({"JP", "KR"}),
    9.5: frozenset({"AU"}),
    10.0: frozenset({"AU", "PG"}),
    12.0: frozenset({"NZ", "FJ", "TV", "WF", "MH", "NR", "KI"}),
}

_NON_LOCATION_WORDS = frozenset(
    {
        "anywhere",
        "cloud",
        "cyberspace",
        "distributed",
        "earth",
        "everywhere",
        "global",
        "globally",
        "home",
        "hybrid",
        "internet",
        "mars",
        "metaverse",
        "moon",
        "nowhere",
        "online",
        "orbit",
        "remote",
        "somewhere",
        "space",
        "universe",
        "virtual",
        "world",
        "worldwide",
    }
)
_NON_LOCATION_PHRASES = frozenset(
    {"international space station", "planet earth", "the internet", "the world"}
)
_SUPRANATIONAL_PHRASES = frozenset(
    {
        "africa",
        "apac",
        "asia",
        "asia pacific",
        "balkans",
        "caribbean",
        "cee",
        "central america",
        "emea",
        "europe",
        "european union",
        "latin america",
        "latam",
        "mena",
        "middle east",
        "north america",
        "oceania",
        "scandinavia",
        "south america",
        "south asia",
        "southeast asia",
        "the americas",
    }
)
_AMBIGUOUS_ALIAS_COUNTRIES: dict[str, frozenset[str]] = {
    "georgia": frozenset({"GE", "US"}),
    "jersey": frozenset({"JE", "US"}),
    "korea": frozenset({"KR", "KP"}),
}
_AMBIGUOUS_REGION_NAMES = frozenset({"georgia", "victoria"})
_ORDINARY_CITY_WORDS = frozenset(
    {"hamilton", "mobile", "nice", "orange", "reading", "split", "victoria"}
)
_BARE_AMBIGUOUS_CITIES = frozenset(
    {
        "athens",
        "cambridge",
        "columbia",
        "dublin",
        "georgetown",
        "george town",
        "hamilton",
        "jerusalem",
        "القدس",
        "ירושלים",
        "kingston",
        "melbourne",
        "plymouth",
        "reading",
        "richmond",
        "san jose",
        "victoria",
    }
)
_EXTERNAL_CITY_BLOCKLIST = frozenset(
    {"atlantis", "bay", "gotham", "mars", "metropolis", "moon", "paradise", "solana"}
)


@dataclass(frozen=True)
class GeoResult:
    country_iso: str | None
    confidence: str
    raw_location: str | None


@dataclass(frozen=True)
class _PlaceHit:
    phrase: str
    countries: frozenset[str]
    primary_country: str | None = None


@dataclass(frozen=True)
class _CodeToken:
    code: str
    isolated: bool
    uppercase: bool


@dataclass(frozen=True)
class _Outcome:
    country_iso: str | None
    confidence: str
    ambiguous: bool = False


def _decompose(text: str) -> str:
    """Fold Latin accents while preserving meaningful marks in other scripts."""
    out: list[str] = []
    previous_base_is_latin = False
    for char in unicodedata.normalize("NFKD", text):
        category = unicodedata.category(char)
        if category.startswith("M"):
            if not previous_base_is_latin:
                out.append(char)
            continue
        previous_base_is_latin = "LATIN" in unicodedata.name(char, "")
        out.append(char)
    return "".join(out)


def _clean(text: str, *, keep_flags: bool) -> str:
    text = _DOTTED_ACRONYM.sub(lambda match: match.group().replace(".", "") + " ", text)
    text = _decompose(text.replace("&", " and ")).lower().translate(_FOLD_CHARS)
    parts: list[str] = []
    for char in text:
        category = unicodedata.category(char)
        keep = char.isalnum() or char.isspace() or category.startswith("M")
        if keep and char not in _SKIPPED_MARKS:
            parts.append(char)
        elif keep_flags and ord(char) in _REGIONAL_INDICATORS:
            parts.append(char)
        else:
            parts.append(" ")
    return " ".join("".join(parts).split())


def _codes_from_raw(raw: str) -> frozenset[str]:
    return frozenset(line.strip().partition(" ")[0] for line in raw.strip().splitlines())


def _build_aliases(raw: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in raw.strip().splitlines():
        code, _, rest = line.strip().partition(" ")
        for alias in rest.split("|"):
            cleaned = _clean(alias, keep_flags=False)
            if cleaned:
                table.setdefault(cleaned, code)
    for alias, code in _SCRIPT_COUNTRY_ALIASES.items():
        cleaned = _clean(alias, keep_flags=False)
        if cleaned:
            table.setdefault(cleaned, code)
    return table


def _build_cities(raw: str) -> tuple[dict[str, frozenset[str]], dict[str, str]]:
    mutable: dict[str, set[str]] = {}
    primary: dict[str, str] = {}
    for line in raw.strip().splitlines():
        code, _, rest = line.strip().partition(" ")
        for city in rest.split("|"):
            cleaned = _clean(city, keep_flags=False)
            if cleaned:
                mutable.setdefault(cleaned, set()).add(code)
                primary.setdefault(cleaned, code)
    for city, code in _SCRIPT_CITY_ALIASES.items():
        cleaned = _clean(city, keep_flags=False)
        if cleaned:
            mutable.setdefault(cleaned, set()).add(code)
            primary.setdefault(cleaned, code)
    # Known cross-country collisions omitted by compact gazetteers. Bare forms
    # stay unresolved; a country, region or code can narrow them safely.
    collisions = {
        "athens": {"GR", "US"},
        "cambridge": {"GB", "US"},
        "columbia": {"CO", "US"},
        "dublin": {"IE", "US"},
        "georgetown": {"GY", "KY", "MY", "US"},
        "george town": {"KY", "MY"},
        "hamilton": {"BM", "CA", "NZ"},
        "jerusalem": {"IL", "PS"},
        "القدس": {"IL", "PS"},
        "ירושלים": {"IL", "PS"},
        "kingston": {"CA", "JM", "NF"},
        "london": {"CA", "GB", "US"},
        "melbourne": {"AU", "US"},
        "paris": {"FR", "US"},
        "plymouth": {"GB", "MS", "US"},
        "reading": {"GB", "US"},
        "richmond": {"AU", "CA", "GB", "US"},
        "san jose": {"CR", "US"},
        "victoria": {"AU", "CA", "SC"},
    }
    for city, countries in collisions.items():
        mutable.setdefault(city, set()).update(countries)
    collision_primaries = {
        "athens": "GR",
        "cambridge": "GB",
        "columbia": "US",
        "dublin": "IE",
        "georgetown": "GY",
        "george town": "MY",
        "hamilton": "CA",
        "kingston": "JM",
        "london": "GB",
        "melbourne": "AU",
        "paris": "FR",
        "plymouth": "GB",
        "reading": "GB",
        "richmond": "US",
        "san jose": "US",
        "victoria": "CA",
    }
    for city, country in collision_primaries.items():
        primary.setdefault(city, country)
    return (
        {city: frozenset(countries) for city, countries in mutable.items()},
        primary,
    )


KNOWN_ISO_CODES: frozenset[str] = _codes_from_raw(_COUNTRY_ALIASES_RAW)
_COUNTRY_ALIASES = _build_aliases(_COUNTRY_ALIASES_RAW + "\n" + _EXTRA_COUNTRY_ALIASES_RAW)
_CITY_COUNTRIES, _CITY_PRIMARY = _build_cities(_GAZETTEER_RAW + "\n" + _EXTRA_CITIES_RAW)
_EXTERNAL_CITY_INDEX: dict[str, tuple[frozenset[str], str | None]] | None = None
_EXTERNAL_CITY_LOCK = threading.Lock()
_ISO_CODES_LOWER = frozenset(code.lower() for code in KNOWN_ISO_CODES)
_GENERICIZED_CC_TLDS = frozenset(
    {
        "ad",
        "ai",
        "as",
        "bz",
        "cc",
        "cd",
        "co",
        "dj",
        "fm",
        "gg",
        "io",
        "la",
        "ly",
        "me",
        "ms",
        "nu",
        "sc",
        "sh",
        "so",
        "tk",
        "to",
        "tv",
        "ws",
    }
)
_CC_TLDS = {
    code.lower(): code for code in KNOWN_ISO_CODES if code.lower() not in _GENERICIZED_CC_TLDS
}
_CC_TLDS["uk"] = "GB"


def _add_region_codes(target: dict[str, set[str]], country: str, codes: str) -> None:
    for code in codes.split():
        target.setdefault(code, set()).add(country)


_REGION_CODES_MUTABLE: dict[str, set[str]] = {}
_add_region_codes(
    _REGION_CODES_MUTABLE,
    "US",
    "al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne "
    "nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy dc",
)
_add_region_codes(_REGION_CODES_MUTABLE, "CA", "ab bc mb nb nl ns nt nu on pe qc sk yt")
_add_region_codes(_REGION_CODES_MUTABLE, "AU", "nsw vic qld wa sa tas act nt")
_add_region_codes(
    _REGION_CODES_MUTABLE,
    "DE",
    "bw by be bb hb he hh mv ni nw rp sl sn st sh th",
)
_add_region_codes(
    _REGION_CODES_MUTABLE,
    "CN",
    "ah bj cq fj gd gs gz ha hb he hi hk hn jl js jx ln nm nx qh sc sd sh sn sx tj " "xj xz yn zj",
)
_add_region_codes(_REGION_CODES_MUTABLE, "GB", "mk")
_add_region_codes(_REGION_CODES_MUTABLE, "IT", "ao")
_add_region_codes(
    _REGION_CODES_MUTABLE,
    "BR",
    "ac al ap am ba ce df es go ma mt ms mg pa pb pr pe pi rj rn rs ro rr sc sp se to",
)
_add_region_codes(
    _REGION_CODES_MUTABLE,
    "IN",
    "ap ar as br cg ga gj hr hp jh ka kl mp mh mn ml mz nl od pb rj sk tn ts tr up " "wb",
)
_REGION_CODES = {code: frozenset(countries) for code, countries in _REGION_CODES_MUTABLE.items()}


def _build_region_names() -> dict[str, frozenset[str]]:
    mutable: dict[str, set[str]] = {}

    def add(country: str, names: str) -> None:
        for name in names.split("|"):
            mutable.setdefault(_clean(name, keep_flags=False), set()).add(country)

    add(
        "US",
        "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|"
        "florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|"
        "maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|"
        "nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|"
        "north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|"
        "south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|"
        "wisconsin|wyoming|district of columbia|new england",
    )
    add(
        "CA",
        "alberta|british columbia|manitoba|new brunswick|newfoundland and labrador|"
        "nova scotia|northwest territories|nunavut|ontario|prince edward island|"
        "quebec|saskatchewan|yukon",
    )
    add(
        "AU",
        "new south wales|queensland|south australia|tasmania|victoria|western australia|"
        "australian capital territory|northern territory",
    )
    add(
        "BR",
        "acre|alagoas|amapa|amazonas|bahia|ceara|distrito federal|espirito santo|"
        "goias|maranhao|mato grosso|mato grosso do sul|minas gerais|para|paraiba|"
        "parana|pernambuco|piaui|rio de janeiro|rio grande do norte|rio grande do sul|"
        "rondonia|roraima|santa catarina|sao paulo|sergipe|tocantins",
    )
    add(
        "DE",
        "baden wurttemberg|bavaria|bayern|brandenburg|hesse|hessen|"
        "mecklenburg vorpommern|lower saxony|niedersachsen|north rhine westphalia|"
        "nordrhein westfalen|rhineland palatinate|rheinland pfalz|saarland|saxony|sachsen|"
        "saxony anhalt|sachsen anhalt|schleswig holstein|thuringia|thuringen",
    )
    add(
        "IN",
        "andhra pradesh|arunachal pradesh|assam|bihar|chhattisgarh|goa|gujarat|haryana|"
        "himachal pradesh|jharkhand|karnataka|kerala|madhya pradesh|maharashtra|manipur|"
        "meghalaya|mizoram|nagaland|odisha|punjab|rajasthan|sikkim|tamil nadu|telangana|"
        "tripura|uttar pradesh|uttarakhand|west bengal",
    )
    add(
        "CN",
        "anhui|fujian|gansu|guangdong|guangxi|guizhou|hainan|hebei|"
        "heilongjiang|henan|hubei|hunan|inner mongolia|jiangsu|jiangxi|jilin|liaoning|"
        "ningxia|qinghai|shaanxi|shandong|shanxi|sichuan|xinjiang|"
        "tibet|yunnan|zhejiang",
    )
    add(
        "GB",
        "bedfordshire|berkshire|buckinghamshire|cambridgeshire|cheshire|cornwall|cumbria|"
        "derbyshire|devon|dorset|east sussex|gloucestershire|greater london|"
        "greater manchester|hampshire|herefordshire|hertfordshire|isle of wight|"
        "lancashire|leicestershire|lincolnshire|merseyside|north yorkshire|"
        "northamptonshire|northumberland|nottinghamshire|oxfordshire|shropshire|somerset|"
        "south yorkshire|staffordshire|suffolk|surrey|tyne and wear|warwickshire|"
        "west midlands|west sussex|west yorkshire|wiltshire|worcestershire|yorkshire",
    )
    add("KR", "gyeonggi do|gyeonggi")
    return {name: frozenset(countries) for name, countries in mutable.items()}


_REGION_NAMES = _build_region_names()


def normalize_location(raw: str) -> str:
    return _clean(raw if isinstance(raw, str) else str(raw), keep_flags=True)


def _as_raw(raw: object) -> str | None:
    if raw is None:
        return None
    return raw if isinstance(raw, str) else str(raw)


def _flag_isos(raw: str) -> frozenset[str]:
    found: set[str] = set()
    for match in _TAG_FLAG.finditer(raw):
        name = "".join(chr(ord(char) - _TAG_OFFSET) for char in match.group(1)).lower()
        mapped = _TAG_FLAGS.get(name)
        if mapped is not None:
            found.add(mapped)
    for match in _FLAG_PATTERN.finditer(raw):
        first, second = match.group()
        code = chr(ord(first) - 0x1F1E6 + 0x41) + chr(ord(second) - 0x1F1E6 + 0x41)
        if code in KNOWN_ISO_CODES:
            found.add(code)
    return frozenset(found)


def _add_candidate(out: list[str], value: str) -> None:
    value = " ".join(value.split())
    if value and value not in out:
        out.append(value)


def _split_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    without_flags = _TAG_FLAG.sub(" ", _FLAG_PATTERN.sub(" ", raw))
    _add_candidate(candidates, _clean(without_flags, keep_flags=False))
    for part in _CANDIDATE_SPLIT.split(without_flags):
        cleaned = _clean(part, keep_flags=False)
        _add_candidate(candidates, cleaned)
        trailing_code = re.fullmatch(r"(.+?)\s+[A-Z]{2}\s*", part.strip())
        if trailing_code is not None:
            _add_candidate(
                candidates,
                _clean(trailing_code.group(1), keep_flags=False),
            )
        for fragment in _PHRASE_SPLIT.split(cleaned):
            _add_candidate(candidates, fragment)
    return candidates


def _ngrams(candidate: str) -> Iterator[tuple[str, int, int, int]]:
    words = candidate.split()
    for size in range(len(words), 0, -1):
        for start in range(0, len(words) - size + 1):
            yield " ".join(words[start : start + size]), size, start, start + size


def _valid_iso(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    code = {"EL": "GR", "UK": "GB"}.get(code, code)
    if len(code) == 2 and code.isascii() and code.isalpha() and code in KNOWN_ISO_CODES:
        return code
    return None


def _external_city_index() -> dict[str, tuple[frozenset[str], str | None]]:
    global _EXTERNAL_CITY_INDEX
    if _EXTERNAL_CITY_INDEX is not None:
        return _EXTERNAL_CITY_INDEX
    with _EXTERNAL_CITY_LOCK:
        if _EXTERNAL_CITY_INDEX is not None:
            return _EXTERNAL_CITY_INDEX
        countries: dict[str, set[str]] = {}
        populations: dict[str, dict[str, int]] = {}
        for city in geonamescache.GeonamesCache().get_cities().values():
            name = _clean(str(city.get("name") or ""), keep_flags=False)
            code = str(city.get("countrycode") or "").upper()
            if len(name) < 3 or code not in KNOWN_ISO_CODES:
                continue
            countries.setdefault(name, set()).add(code)
            population = int(city.get("population") or 0)
            by_country = populations.setdefault(name, {})
            by_country[code] = max(population, by_country.get(code, 0))
        index: dict[str, tuple[frozenset[str], str | None]] = {}
        for name, codes in countries.items():
            ranked = sorted(populations[name].items(), key=lambda item: item[1], reverse=True)
            dominant = ranked[0][0]
            if len(ranked) > 1 and ranked[0][1] < ranked[1][1] * 3:
                dominant = None
            index[name] = frozenset(codes), dominant
        _EXTERNAL_CITY_INDEX = index
        return _EXTERNAL_CITY_INDEX


def _lookup_city(
    phrase: str,
    gazetteer: Mapping[str, str] | None,
    *,
    allow_external: bool,
) -> tuple[frozenset[str], str | None] | None:
    if gazetteer is not None:
        custom = _valid_iso(gazetteer.get(phrase))
        if custom is not None:
            return frozenset({custom}), custom
    if (
        phrase in _EXTERNAL_CITY_BLOCKLIST
        or phrase in _NON_LOCATION_WORDS
        or phrase in _NON_LOCATION_PHRASES
        or phrase in _SUPRANATIONAL_PHRASES
    ):
        return None
    if phrase in _COUNTRY_ALIASES and phrase not in _AMBIGUOUS_ALIAS_COUNTRIES:
        return None
    countries = _CITY_COUNTRIES.get(phrase)
    external = _external_city_index().get(phrase) if allow_external else None
    if countries is None:
        return external
    if external is None:
        return countries, _CITY_PRIMARY[phrase]
    return countries | external[0], _CITY_PRIMARY[phrase]


def _select_non_overlapping(
    candidate: str,
    lookup: Callable[[str], frozenset[str] | tuple[frozenset[str], str | None] | None],
) -> list[_PlaceHit]:
    selected: list[_PlaceHit] = []
    spans: list[tuple[int, int]] = []
    for phrase, _size, start, end in _ngrams(candidate):
        if any(start < used_end and end > used_start for used_start, used_end in spans):
            continue
        looked_up = lookup(phrase)
        if looked_up is None:
            continue
        if isinstance(looked_up, tuple):
            countries, primary = looked_up
        else:
            countries, primary = looked_up, None
        selected.append(_PlaceHit(phrase, countries, primary))
        spans.append((start, end))
    return selected


def _city_hits(candidates: Sequence[str], gazetteer: Mapping[str, str] | None) -> list[_PlaceHit]:
    found: dict[str, _PlaceHit] = {}
    for candidate in candidates:
        if candidate in _NON_LOCATION_WORDS or candidate in _NON_LOCATION_PHRASES:
            continue
        candidate_words = set(candidate.split())
        for hit in _select_non_overlapping(
            candidate,
            lambda phrase, candidate=candidate: _lookup_city(
                phrase,
                gazetteer,
                allow_external=phrase == candidate,
            ),
        ):
            if re.search(rf"\bnot\s+{re.escape(hit.phrase)}\b", candidate):
                continue
            if (
                hit.phrase in _ORDINARY_CITY_WORDS
                and candidate != hit.phrase
                and candidate_words & _NON_LOCATION_WORDS
            ):
                continue
            previous = found.get(hit.phrase)
            if previous is None:
                found[hit.phrase] = hit
            else:
                found[hit.phrase] = _PlaceHit(
                    hit.phrase,
                    previous.countries | hit.countries,
                    previous.primary_country or hit.primary_country,
                )
    hits = list(found.values())
    return [
        hit
        for hit in hits
        if not any(
            hit.phrase != other.phrase
            and _phrase_contains(other.phrase, hit.phrase)
            and len(other.phrase.split()) > len(hit.phrase.split())
            for other in hits
        )
    ]


def _region_hits(candidates: Sequence[str], city_hits: Sequence[_PlaceHit]) -> list[_PlaceHit]:
    found: list[_PlaceHit] = []
    seen: set[tuple[str, frozenset[str]]] = set()
    for candidate in candidates:
        for hit in _select_non_overlapping(candidate, _REGION_NAMES.get):
            # A subdivision is reliable as a complete fragment or trailing
            # qualifier. This avoids matching arbitrary institution prose.
            if candidate != hit.phrase and not candidate.endswith(" " + hit.phrase):
                continue
            if hit.phrase in _AMBIGUOUS_REGION_NAMES and not any(
                city.phrase != hit.phrase and bool(city.countries & hit.countries)
                for city in city_hits
            ):
                continue
            key = (hit.phrase, hit.countries)
            if key not in seen:
                seen.add(key)
                found.append(hit)
    return found


def _phrase_contains(container: str, phrase: str) -> bool:
    return f" {phrase} " in f" {container} "


def _country_hits(candidates: Sequence[str], place_hits: Sequence[_PlaceHit]) -> list[_PlaceHit]:
    found: list[_PlaceHit] = []
    seen: set[tuple[str, frozenset[str]]] = set()
    for candidate in candidates:
        supranational = [
            (start, end)
            for phrase, _size, start, end in _ngrams(candidate)
            if phrase in _SUPRANATIONAL_PHRASES
        ]
        spans: list[tuple[int, int]] = []
        for phrase, _size, start, end in _ngrams(candidate):
            if any(start < used_end and end > used_start for used_start, used_end in spans):
                continue
            iso = _COUNTRY_ALIASES.get(phrase)
            if iso is None:
                continue
            if phrase in _AMBIGUOUS_ALIAS_COUNTRIES:
                continue
            if any(
                start >= supra_start and end <= supra_end
                for supra_start, supra_end in supranational
            ):
                continue
            if phrase == "us" and candidate != "us" and not candidate.startswith("us "):
                continue
            if any(
                phrase != place.phrase
                and _phrase_contains(place.phrase, phrase)
                and iso not in place.countries
                for place in place_hits
            ):
                continue
            hit = _PlaceHit(phrase, frozenset({iso}))
            key = (hit.phrase, hit.countries)
            if key not in seen:
                seen.add(key)
                found.append(hit)
            spans.append((start, end))
    return [
        hit
        for hit in found
        if not any(
            hit.phrase != other.phrase
            and _phrase_contains(other.phrase, hit.phrase)
            and len(other.phrase.split()) > len(hit.phrase.split())
            for other in found
        )
    ]


def _options(hits: Sequence[_PlaceHit]) -> tuple[frozenset[str], bool]:
    if not hits:
        return frozenset(), False
    common = set(hits[0].countries)
    for hit in hits[1:]:
        common.intersection_update(hit.countries)
    return frozenset(common), not common


def _city_options(hits: Sequence[_PlaceHit]) -> tuple[frozenset[str], bool]:
    options, conflict = _options(hits)
    primaries = {hit.primary_country for hit in hits if hit.primary_country is not None}
    if len(primaries) > 1:
        return options, True
    return options, conflict


def _extract_code_tokens(raw: str) -> list[_CodeToken]:
    without_flags = _TAG_FLAG.sub(" ", _FLAG_PATTERN.sub(" ", raw))
    tokens: list[_CodeToken] = []
    seen: set[tuple[str, bool, bool]] = set()
    parts = [part.strip() for part in _CANDIDATE_SPLIT.split(without_flags) if part.strip()]
    for part in parts:
        if re.fullmatch(r"[A-Za-z]{2}", part) is None:
            continue
        key = (part.upper(), len(parts) > 1, part.isupper())
        if key not in seen:
            seen.add(key)
            tokens.append(_CodeToken(*key))
    whole = without_flags.strip()
    if re.fullmatch(r"[A-Za-z]{2}", whole):
        key = (whole.upper(), True, whole.isupper())
        if key not in seen:
            seen.add(key)
            tokens.append(_CodeToken(*key))
    trailing = re.search(r"(?:^|\s)([A-Z]{2})\s*$", without_flags)
    if trailing is not None:
        key = (trailing.group(1), False, True)
        if key not in seen:
            tokens.append(_CodeToken(*key))
    return tokens


def _code_hits(raw: str, *, contextual: bool) -> tuple[list[_PlaceHit], dict[str, str], bool]:
    hits: list[_PlaceHit] = []
    methods: dict[str, str] = {}
    unresolved_collision = False
    for token in _extract_code_tokens(raw):
        if not token.isolated and not contextual:
            continue
        lowered = token.code.lower()
        iso = token.code if token.code in KNOWN_ISO_CODES else None
        regions = _REGION_CODES.get(lowered, frozenset())
        possible = set(regions)
        if iso is not None:
            possible.add(iso)
        if not possible:
            continue
        hits.append(_PlaceHit(token.code.lower(), frozenset(possible)))
        for country in possible:
            if country == iso and country not in regions:
                methods[country] = "exact-iso"
            elif country != iso:
                methods.setdefault(country, "region")
        if iso is not None and regions and token.uppercase:
            unresolved_collision = True
    return hits, methods, unresolved_collision


def _blog_iso(blog: str | None) -> str | None:
    if not isinstance(blog, str) or not blog.strip():
        return None
    url = blog if "://" in blog else f"https://{blog}"
    host = urlparse(url).hostname or ""
    if "." not in host:
        return None
    return _CC_TLDS.get(host.rsplit(".", 1)[-1].lower())


def _tz_iso(tz_offset: float | None) -> str | None:
    if tz_offset is None:
        return None
    try:
        offset = float(tz_offset)
    except (TypeError, ValueError, OverflowError):
        return None
    scaled = offset * 4
    if not math.isfinite(offset) or not math.isfinite(scaled):
        return None
    key = round(scaled) / 4
    codes = _TZ_BANDS.get(key)
    if codes is not None and len(codes) == 1:
        return next(iter(codes))
    return None


def _weak_options(blog: str | None, tz_offset: float | None) -> frozenset[str]:
    return frozenset(iso for iso in (_blog_iso(blog), _tz_iso(tz_offset)) if iso is not None)


def _contains_non_location(candidates: Sequence[str]) -> bool:
    return any(
        candidate in _NON_LOCATION_PHRASES or bool(set(candidate.split()) & _NON_LOCATION_WORDS)
        for candidate in candidates
    )


def _contains_supranational(candidates: Sequence[str]) -> bool:
    return any(
        phrase in _SUPRANATIONAL_PHRASES
        for candidate in candidates
        for phrase, _size, _start, _end in _ngrams(candidate)
    )


def _text_outcome(
    original: str | None,
    *,
    gazetteer: Mapping[str, str] | None,
    geocoder: Callable[[str], str | None] | None,
    blog: str | None,
    tz_offset: float | None,
) -> _Outcome:
    location_text = _CONTACT_LIKE.sub(" ", original) if original is not None else None
    candidates = _split_candidates(location_text) if location_text is not None else []
    contact_only = original is not None and not candidates

    city_hits = _city_hits(candidates, gazetteer)
    region_hits = _region_hits(candidates, city_hits)
    city_hits = [
        city
        for city in city_hits
        if not any(
            (
                city.phrase != region.phrase
                and _phrase_contains(region.phrase, city.phrase)
                and not bool(city.countries & region.countries)
            )
            or (
                city.phrase == region.phrase
                and city.phrase in _AMBIGUOUS_REGION_NAMES
                and any(
                    other.phrase != city.phrase and bool(other.countries & region.countries)
                    for other in city_hits
                )
            )
            for region in region_hits
        )
    ]
    country_hits = _country_hits(candidates, [*city_hits, *region_hits])
    city_hits = [
        city
        for city in city_hits
        if not any(
            city.phrase != country.phrase
            and _phrase_contains(country.phrase, city.phrase)
            and not bool(city.countries & country.countries)
            for country in country_hits
        )
    ]
    code_hits, code_methods, unresolved_code_collision = (
        _code_hits(
            location_text,
            contextual=bool(city_hits or region_hits or country_hits),
        )
        if location_text is not None and not contact_only
        else ([], {}, False)
    )

    name_options, name_conflict = _options(country_hits)
    region_options, region_conflict = _options(region_hits)
    city_options, city_conflict = _city_options(city_hits)
    code_options, code_conflict = _options(code_hits)
    if name_conflict or region_conflict or city_conflict or code_conflict:
        return _Outcome(None, "unmatched", ambiguous=True)

    evidence = [
        options for options in (name_options, region_options, code_options, city_options) if options
    ]
    if evidence:
        common = set(evidence[0])
        for options in evidence[1:]:
            common.intersection_update(options)
        if len(common) != 1:
            city_primaries = {
                hit.primary_country for hit in city_hits if hit.primary_country is not None
            }
            if (
                len(evidence) == 1
                and len(city_primaries) == 1
                and all(hit.phrase not in _BARE_AMBIGUOUS_CITIES for hit in city_hits)
            ):
                return _Outcome(next(iter(city_primaries)), "gazetteer-city")
            weak = _weak_options(blog, tz_offset)
            if len(common) > 1 and len(weak) == 1:
                weak_country = next(iter(weak))
                if weak_country in common:
                    return _Outcome(weak_country, "weak")
            # A bare two-letter token colliding with a subdivision is not safe
            # to guess. Explicit contextual evidence above can still narrow it.
            return _Outcome(None, "unmatched", ambiguous=True)
        country = next(iter(common))
        if unresolved_code_collision and len(evidence) == 1 and code_options:
            return _Outcome(None, "unmatched", ambiguous=True)
        if country in code_methods and code_methods[country] == "exact-iso":
            return _Outcome(country, "exact-iso")
        if name_options:
            return _Outcome(country, "name")
        if region_options or code_methods.get(country) == "region":
            return _Outcome(country, "region")
        return _Outcome(country, "gazetteer-city")

    if _contains_supranational(candidates) or _contains_non_location(candidates):
        return _Outcome(None, "unmatched")

    if geocoder is not None:
        geocoded: set[str] = set()
        for candidate in candidates:
            iso = _valid_iso(geocoder(candidate))
            if iso is not None:
                geocoded.add(iso)
        if len(geocoded) == 1:
            return _Outcome(next(iter(geocoded)), "geocoder")
        if len(geocoded) > 1:
            return _Outcome(None, "unmatched", ambiguous=True)

    weak = _weak_options(blog, tz_offset)
    if len(weak) == 1:
        return _Outcome(next(iter(weak)), "weak")
    if len(weak) > 1:
        return _Outcome(None, "unmatched")
    return _Outcome(None, "unmatched")


def resolve_location(
    raw: str | None,
    *,
    gazetteer: Mapping[str, str] | None = None,
    geocoder: Callable[[str], str | None] | None = None,
    blog: str | None = None,
    tz_offset: float | None = None,
) -> GeoResult:
    """Resolve free-form profile location conservatively to ISO alpha-2.

    Independent strong signals must agree. Conflicting countries, ambiguous
    bare cities/codes, non-locations and supranational regions deliberately
    return ``unmatched``: for corpus filtering, a false country is worse than
    an honest unknown.
    """
    original = _as_raw(raw)
    if original is not None and len(original) > _MAX_LOCATION_CHARS:
        return GeoResult(None, "unmatched", original)
    flags = _flag_isos(original) if original is not None else frozenset()
    if len(flags) > 1:
        return GeoResult(None, "unmatched", original)
    outcome = _text_outcome(
        original,
        gazetteer=gazetteer,
        geocoder=geocoder,
        blog=blog,
        tz_offset=tz_offset,
    )
    if flags:
        flag = next(iter(flags))
        if outcome.ambiguous:
            return GeoResult(None, "unmatched", original)
        if outcome.country_iso is not None and outcome.country_iso != flag:
            if outcome.confidence == "weak":
                return GeoResult(flag, "exact-iso", original)
            return GeoResult(None, "unmatched", original)
        return GeoResult(flag, "exact-iso", original)
    return GeoResult(outcome.country_iso, outcome.confidence, original)


_MEMO_MAX = 4096
_MEMO: OrderedDict[str, GeoResult] = OrderedDict()
_MEMO_LOCK = threading.RLock()


def _cache_key(raw: str | None) -> str:
    cleaned = _as_raw(raw)
    return normalize_location(cleaned) if cleaned is not None else ""


def _owner_cache_key(raw: str | None, blog: str | None, tz_offset: float | None) -> str:
    key = _cache_key(raw)
    extras: list[str] = []
    blog_iso = _blog_iso(blog)
    timezone_iso = _tz_iso(tz_offset)
    if blog_iso is not None:
        extras.append("blog=" + blog_iso)
    if timezone_iso is not None:
        extras.append("tz=" + timezone_iso)
    return key if not extras else key + "\x1f" + "\x1f".join(extras)


def _memo_get(key: str) -> GeoResult | None:
    with _MEMO_LOCK:
        result = _MEMO.get(key)
        if result is not None:
            _MEMO.move_to_end(key)
        return result


def _memo_put(key: str, result: GeoResult) -> None:
    with _MEMO_LOCK:
        _MEMO[key] = result
        _MEMO.move_to_end(key)
        while len(_MEMO) > _MEMO_MAX:
            _MEMO.popitem(last=False)


class GeoCache:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, normalized: str) -> GeoResult | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                sa.select(
                    GeoCacheRow.country_iso,
                    GeoCacheRow.confidence,
                    GeoCacheRow.raw_sample,
                ).where(
                    GeoCacheRow.normalized == normalized,
                    GeoCacheRow.resolver_version == GEO_RESOLVER_VERSION,
                )
            ).first()
        if row is None:
            return None
        return GeoResult(row.country_iso, row.confidence, row.raw_sample)

    def put(self, normalized: str, result: GeoResult) -> None:
        base = pg_insert(GeoCacheRow).values(
            normalized=normalized,
            country_iso=result.country_iso,
            confidence=result.confidence,
            raw_sample=result.raw_location,
            resolver_version=GEO_RESOLVER_VERSION,
            hits=1,
        )
        statement = base.on_conflict_do_update(
            index_elements=[GeoCacheRow.normalized],
            set_={
                "country_iso": base.excluded.country_iso,
                "confidence": base.excluded.confidence,
                "raw_sample": base.excluded.raw_sample,
                "resolver_version": GEO_RESOLVER_VERSION,
                "hits": GeoCacheRow.hits + 1,
                "updated_at": sa.func.now(),
            },
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def get_many(self, keys: Sequence[str], *, batch_size: int = 1000) -> dict[str, GeoResult]:
        if not keys:
            return {}
        found: dict[str, GeoResult] = {}
        with self._engine.connect() as connection:
            for batch in chunked(keys, batch_size):
                rows = connection.execute(
                    sa.select(
                        GeoCacheRow.normalized,
                        GeoCacheRow.country_iso,
                        GeoCacheRow.confidence,
                        GeoCacheRow.raw_sample,
                    ).where(
                        GeoCacheRow.normalized.in_(batch),
                        GeoCacheRow.resolver_version == GEO_RESOLVER_VERSION,
                    )
                ).all()
                for normalized, country_iso, confidence, raw_sample in rows:
                    found[str(normalized)] = GeoResult(country_iso, confidence, raw_sample)
        return found

    def put_many(self, results: Mapping[str, GeoResult], *, batch_size: int = 1000) -> None:
        if not results:
            return
        for batch in chunked(list(results.items()), batch_size):
            values = [
                {
                    "normalized": key,
                    "country_iso": result.country_iso,
                    "confidence": result.confidence,
                    "raw_sample": result.raw_location,
                    "resolver_version": GEO_RESOLVER_VERSION,
                    "hits": 1,
                }
                for key, result in batch
            ]
            base = pg_insert(GeoCacheRow).values(values)
            statement = base.on_conflict_do_update(
                index_elements=[GeoCacheRow.normalized],
                set_={
                    "country_iso": base.excluded.country_iso,
                    "confidence": base.excluded.confidence,
                    "raw_sample": base.excluded.raw_sample,
                    "resolver_version": GEO_RESOLVER_VERSION,
                    "hits": GeoCacheRow.hits + 1,
                    "updated_at": sa.func.now(),
                },
            )
            with self._engine.begin() as connection:
                connection.execute(statement)


def resolve_many(
    engine: Engine,
    raw_locations: Sequence[str | None],
    *,
    blogs: Sequence[str | None] | None = None,
    cache: GeoCache | None = None,
) -> dict[str | None, GeoResult]:
    if not raw_locations:
        return {}
    if blogs is not None and len(blogs) != len(raw_locations):
        raise ValueError("blogs must have the same length as raw_locations")
    store = cache or GeoCache(engine)
    blog_values = list(blogs) if blogs is not None else [None] * len(raw_locations)
    keys = [
        _owner_cache_key(raw, blog, None)
        for raw, blog in zip(raw_locations, blog_values, strict=True)
    ]
    profile_by_key: dict[str, tuple[str | None, str | None]] = {}
    for key, raw, blog in zip(keys, raw_locations, blog_values, strict=True):
        profile_by_key.setdefault(key, (raw, blog))
    unique = list(profile_by_key)
    cached = store.get_many(unique)
    results: dict[str, GeoResult] = dict(cached)
    fresh: dict[str, GeoResult] = {}
    for key in unique:
        if key in results:
            continue
        memo = _memo_get(key)
        if memo is None:
            raw, blog = profile_by_key[key]
            memo = resolve_location(_as_raw(raw), blog=blog)
            _memo_put(key, memo)
        # Repopulate a missing durable cache row even on a process-memo hit.
        fresh[key] = memo
        results[key] = memo
    if fresh:
        store.put_many(fresh)
    return results


def resolve_owner(
    engine: Engine,
    raw_location: str | None,
    *,
    gazetteer: Mapping[str, str] | None = None,
    geocoder: Callable[[str], str | None] | None = None,
    blog: str | None = None,
    tz_offset: float | None = None,
) -> GeoResult:
    cache = GeoCache(engine)
    raw = _as_raw(raw_location)
    key = _owner_cache_key(raw, blog, tz_offset)
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = resolve_location(
        raw,
        gazetteer=gazetteer,
        geocoder=geocoder,
        blog=blog,
        tz_offset=tz_offset,
    )
    cache.put(key, result)
    return result
