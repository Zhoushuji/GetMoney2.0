export type GeoEntry = {
  code: string;
  name_en: string;
  name_local: string;
  name_zh: string;
  continent: string;
  languages: string[];
};

export const CONTINENTS = ["Africa", "Asia", "Europe", "North America", "South America", "Oceania"] as const;

export const LANGUAGE_LABELS: Record<string, string> = {
  "en": "English",
  "ar": "Arabic",
  "fr": "French",
  "pt": "Portuguese",
  "rn": "Kirundi",
  "tn": "Tswana",
  "sg": "Sango",
  "sw": "Swahili",
  "ln": "Lingala",
  "kg": "Kongo",
  "ti": "Tigrinya",
  "am": "Amharic",
  "wo": "Wolof",
  "kea": "Cape Verdean Creole",
  "rw": "Kinyarwanda",
  "mg": "Malagasy",
  "ny": "Chichewa",
  "bm": "Bambara",
  "mfe": "Mauritian Creole",
  "tzm": "Tamazight",
  "ha": "Hausa",
  "yo": "Yoruba",
  "ig": "Igbo",
  "so": "Somali",
  "zu": "Zulu",
  "xh": "Xhosa",
  "af": "Afrikaans",
  "nso": "Northern Sotho",
  "st": "Southern Sotho",
  "ts": "Tsonga",
  "ss": "Swati",
  "ve": "Venda",
  "nr": "Southern Ndebele",
  "fa": "Persian",
  "ps": "Pashto",
  "hy": "Armenian",
  "az": "Azerbaijani",
  "bn": "Bengali",
  "dz": "Dzongkha",
  "ms": "Malay",
  "km": "Khmer",
  "zh": "Chinese",
  "el": "Greek",
  "tr": "Turkish",
  "ka": "Georgian",
  "hi": "Hindi",
  "id": "Indonesian",
  "he": "Hebrew",
  "ja": "Japanese",
  "kk": "Kazakh",
  "ky": "Kyrgyz",
  "ru": "Russian",
  "lo": "Lao",
  "dv": "Dhivehi",
  "mn": "Mongolian",
  "my": "Burmese",
  "ne": "Nepali",
  "ko": "Korean",
  "ur": "Urdu",
  "fil": "Filipino",
  "si": "Sinhala",
  "ta": "Tamil",
  "tg": "Tajik",
  "th": "Thai",
  "tet": "Tetum",
  "tk": "Turkmen",
  "uz": "Uzbek",
  "vi": "Vietnamese",
  "sq": "Albanian",
  "ca": "Catalan",
  "be": "Belarusian",
  "nl": "Dutch",
  "bs": "Bosnian",
  "hr": "Croatian",
  "sr": "Serbian",
  "bg": "Bulgarian",
  "cs": "Czech",
  "da": "Danish",
  "et": "Estonian",
  "fi": "Finnish",
  "sv": "Swedish",
  "de": "German",
  "hu": "Hungarian",
  "is": "Icelandic",
  "ga": "Irish",
  "lv": "Latvian",
  "lt": "Lithuanian",
  "lb": "Luxembourgish",
  "ro": "Romanian",
  "me": "Montenegrin",
  "no": "Norwegian",
  "pl": "Polish",
  "sl": "Slovenian",
  "uk": "Ukrainian",
  "cy": "Welsh",
  "gd": "Scottish Gaelic",
  "la": "Latin",
  "es": "Spanish",
  "eu": "Basque",
  "gl": "Galician",
  "qu": "Quechua",
  "ay": "Aymara",
  "gn": "Guarani",
  "ht": "Haitian Creole",
  "fj": "Fijian",
  "gil": "Gilbertese",
  "mh": "Marshallese",
  "na": "Nauruan",
  "mi": "Māori",
  "pau": "Palauan",
  "tpi": "Tok Pisin",
  "ho": "Hiri Motu",
  "sm": "Samoan",
  "to": "Tongan",
  "tvl": "Tuvaluan",
  "bi": "Bislama",
  "cri": "Guinea-Bissau Creole",
  "rm": "Romansh",
  "ku": "Kurdish",
  "nd": "North Ndebele",
  "mt": "Maltese"
};

const rawGeoData: Array<Omit<GeoEntry, "name_zh">> = [
  {
    "code": "DZ",
    "name_en": "Algeria",
    "name_local": "Algeria",
    "continent": "Africa",
    "languages": [
      "ar",
      "fr",
      "en"
    ]
  },
  {
    "code": "AO",
    "name_en": "Angola",
    "name_local": "Angola",
    "continent": "Africa",
    "languages": [
      "pt",
      "en"
    ]
  },
  {
    "code": "BJ",
    "name_en": "Benin",
    "name_local": "Bénin",
    "continent": "Africa",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "BW",
    "name_en": "Botswana",
    "name_local": "Botswana",
    "continent": "Africa",
    "languages": [
      "en",
      "tn"
    ]
  },
  {
    "code": "BF",
    "name_en": "Burkina Faso",
    "name_local": "Burkina Faso",
    "continent": "Africa",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "BI",
    "name_en": "Burundi",
    "name_local": "Burundi",
    "continent": "Africa",
    "languages": [
      "rn",
      "fr",
      "en"
    ]
  },
  {
    "code": "CM",
    "name_en": "Cameroon",
    "name_local": "Cameroun",
    "continent": "Africa",
    "languages": [
      "en",
      "fr"
    ]
  },
  {
    "code": "CV",
    "name_en": "Cape Verde",
    "name_local": "Cabo Verde",
    "continent": "Africa",
    "languages": [
      "pt",
      "kea",
      "en"
    ]
  },
  {
    "code": "CF",
    "name_en": "Central African Republic",
    "name_local": "République centrafricaine",
    "continent": "Africa",
    "languages": [
      "fr",
      "sg",
      "en"
    ]
  },
  {
    "code": "TD",
    "name_en": "Chad",
    "name_local": "Tchad",
    "continent": "Africa",
    "languages": [
      "fr",
      "ar",
      "en"
    ]
  },
  {
    "code": "KM",
    "name_en": "Comoros",
    "name_local": "Komori",
    "continent": "Africa",
    "languages": [
      "ar",
      "fr",
      "sw",
      "en"
    ]
  },
  {
    "code": "CD",
    "name_en": "DR Congo",
    "name_local": "RD Congo",
    "continent": "Africa",
    "languages": [
      "fr",
      "sw",
      "ln",
      "kg"
    ]
  },
  {
    "code": "CG",
    "name_en": "Congo",
    "name_local": "Congo",
    "continent": "Africa",
    "languages": [
      "fr",
      "ln",
      "en"
    ]
  },
  {
    "code": "CI",
    "name_en": "Côte d'Ivoire",
    "name_local": "Côte d'Ivoire",
    "continent": "Africa",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "DJ",
    "name_en": "Djibouti",
    "name_local": "Djibouti",
    "continent": "Africa",
    "languages": [
      "fr",
      "ar",
      "en"
    ]
  },
  {
    "code": "EG",
    "name_en": "Egypt",
    "name_local": "مصر",
    "continent": "Africa",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "GQ",
    "name_en": "Equatorial Guinea",
    "name_local": "Guinea Ecuatorial",
    "continent": "Africa",
    "languages": [
      "es",
      "fr",
      "pt"
    ]
  },
  {
    "code": "ER",
    "name_en": "Eritrea",
    "name_local": "ኤርትራ",
    "continent": "Africa",
    "languages": [
      "ti",
      "ar",
      "en"
    ]
  },
  {
    "code": "ET",
    "name_en": "Ethiopia",
    "name_local": "ኢትዮጵያ",
    "continent": "Africa",
    "languages": [
      "am",
      "en"
    ]
  },
  {
    "code": "GA",
    "name_en": "Gabon",
    "name_local": "Gabon",
    "continent": "Africa",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "GM",
    "name_en": "Gambia",
    "name_local": "Gambia",
    "continent": "Africa",
    "languages": [
      "en"
    ]
  },
  {
    "code": "GH",
    "name_en": "Ghana",
    "name_local": "Ghana",
    "continent": "Africa",
    "languages": [
      "en"
    ]
  },
  {
    "code": "GN",
    "name_en": "Guinea",
    "name_local": "Guinée",
    "continent": "Africa",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "GW",
    "name_en": "Guinea-Bissau",
    "name_local": "Guiné-Bissau",
    "continent": "Africa",
    "languages": [
      "pt",
      "cri",
      "en"
    ]
  },
  {
    "code": "KE",
    "name_en": "Kenya",
    "name_local": "Kenya",
    "continent": "Africa",
    "languages": [
      "en",
      "sw"
    ]
  },
  {
    "code": "LS",
    "name_en": "Lesotho",
    "name_local": "Lesotho",
    "continent": "Africa",
    "languages": [
      "en",
      "st"
    ]
  },
  {
    "code": "LR",
    "name_en": "Liberia",
    "name_local": "Liberia",
    "continent": "Africa",
    "languages": [
      "en"
    ]
  },
  {
    "code": "LY",
    "name_en": "Libya",
    "name_local": "ليبيا",
    "continent": "Africa",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "MG",
    "name_en": "Madagascar",
    "name_local": "Madagasikara",
    "continent": "Africa",
    "languages": [
      "mg",
      "fr",
      "en"
    ]
  },
  {
    "code": "MW",
    "name_en": "Malawi",
    "name_local": "Malawi",
    "continent": "Africa",
    "languages": [
      "en",
      "ny"
    ]
  },
  {
    "code": "ML",
    "name_en": "Mali",
    "name_local": "Mali",
    "continent": "Africa",
    "languages": [
      "fr",
      "bm",
      "en"
    ]
  },
  {
    "code": "MR",
    "name_en": "Mauritania",
    "name_local": "موريتانيا",
    "continent": "Africa",
    "languages": [
      "ar",
      "fr",
      "en"
    ]
  },
  {
    "code": "MU",
    "name_en": "Mauritius",
    "name_local": "Maurice",
    "continent": "Africa",
    "languages": [
      "en",
      "fr",
      "mfe"
    ]
  },
  {
    "code": "MA",
    "name_en": "Morocco",
    "name_local": "المغرب",
    "continent": "Africa",
    "languages": [
      "ar",
      "fr",
      "tzm",
      "en"
    ]
  },
  {
    "code": "MZ",
    "name_en": "Mozambique",
    "name_local": "Moçambique",
    "continent": "Africa",
    "languages": [
      "pt",
      "en"
    ]
  },
  {
    "code": "NA",
    "name_en": "Namibia",
    "name_local": "Namibia",
    "continent": "Africa",
    "languages": [
      "en",
      "af",
      "de"
    ]
  },
  {
    "code": "NE",
    "name_en": "Niger",
    "name_local": "Niger",
    "continent": "Africa",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "NG",
    "name_en": "Nigeria",
    "name_local": "Nigeria",
    "continent": "Africa",
    "languages": [
      "en",
      "ha",
      "yo",
      "ig"
    ]
  },
  {
    "code": "RW",
    "name_en": "Rwanda",
    "name_local": "Rwanda",
    "continent": "Africa",
    "languages": [
      "rw",
      "en",
      "fr"
    ]
  },
  {
    "code": "ST",
    "name_en": "São Tomé and Príncipe",
    "name_local": "São Tomé e Príncipe",
    "continent": "Africa",
    "languages": [
      "pt",
      "en"
    ]
  },
  {
    "code": "SN",
    "name_en": "Senegal",
    "name_local": "Sénégal",
    "continent": "Africa",
    "languages": [
      "fr",
      "wo",
      "en"
    ]
  },
  {
    "code": "SL",
    "name_en": "Sierra Leone",
    "name_local": "Sierra Leone",
    "continent": "Africa",
    "languages": [
      "en"
    ]
  },
  {
    "code": "SO",
    "name_en": "Somalia",
    "name_local": "Soomaaliya",
    "continent": "Africa",
    "languages": [
      "so",
      "ar",
      "en"
    ]
  },
  {
    "code": "ZA",
    "name_en": "South Africa",
    "name_local": "South Africa",
    "continent": "Africa",
    "languages": [
      "zu",
      "xh",
      "af",
      "en",
      "nso",
      "tn",
      "st",
      "ts",
      "ss",
      "ve",
      "nr"
    ]
  },
  {
    "code": "SS",
    "name_en": "South Sudan",
    "name_local": "South Sudan",
    "continent": "Africa",
    "languages": [
      "en",
      "ar"
    ]
  },
  {
    "code": "SD",
    "name_en": "Sudan",
    "name_local": "السودان",
    "continent": "Africa",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "SZ",
    "name_en": "Eswatini",
    "name_local": "eSwatini",
    "continent": "Africa",
    "languages": [
      "en",
      "ss"
    ]
  },
  {
    "code": "TZ",
    "name_en": "Tanzania",
    "name_local": "Tanzania",
    "continent": "Africa",
    "languages": [
      "sw",
      "en"
    ]
  },
  {
    "code": "TG",
    "name_en": "Togo",
    "name_local": "Togo",
    "continent": "Africa",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "TN",
    "name_en": "Tunisia",
    "name_local": "تونس",
    "continent": "Africa",
    "languages": [
      "ar",
      "fr",
      "en"
    ]
  },
  {
    "code": "UG",
    "name_en": "Uganda",
    "name_local": "Uganda",
    "continent": "Africa",
    "languages": [
      "en",
      "sw"
    ]
  },
  {
    "code": "ZM",
    "name_en": "Zambia",
    "name_local": "Zambia",
    "continent": "Africa",
    "languages": [
      "en"
    ]
  },
  {
    "code": "ZW",
    "name_en": "Zimbabwe",
    "name_local": "Zimbabwe",
    "continent": "Africa",
    "languages": [
      "en",
      "sn",
      "nd"
    ]
  },
  {
    "code": "AF",
    "name_en": "Afghanistan",
    "name_local": "افغانستان",
    "continent": "Asia",
    "languages": [
      "fa",
      "ps",
      "en"
    ]
  },
  {
    "code": "AM",
    "name_en": "Armenia",
    "name_local": "Հայաստան",
    "continent": "Asia",
    "languages": [
      "hy",
      "en"
    ]
  },
  {
    "code": "AZ",
    "name_en": "Azerbaijan",
    "name_local": "Azərbaycan",
    "continent": "Asia",
    "languages": [
      "az",
      "en",
      "ru"
    ]
  },
  {
    "code": "BH",
    "name_en": "Bahrain",
    "name_local": "البحرين",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "BD",
    "name_en": "Bangladesh",
    "name_local": "বাংলাদেশ",
    "continent": "Asia",
    "languages": [
      "bn",
      "en"
    ]
  },
  {
    "code": "BT",
    "name_en": "Bhutan",
    "name_local": "འབྲུག",
    "continent": "Asia",
    "languages": [
      "dz",
      "en"
    ]
  },
  {
    "code": "BN",
    "name_en": "Brunei",
    "name_local": "Brunei",
    "continent": "Asia",
    "languages": [
      "ms",
      "en"
    ]
  },
  {
    "code": "KH",
    "name_en": "Cambodia",
    "name_local": "កម្ពុជា",
    "continent": "Asia",
    "languages": [
      "km",
      "en"
    ]
  },
  {
    "code": "CN",
    "name_en": "China",
    "name_local": "中国",
    "continent": "Asia",
    "languages": [
      "zh",
      "en"
    ]
  },
  {
    "code": "CY",
    "name_en": "Cyprus",
    "name_local": "Κύπρος",
    "continent": "Asia",
    "languages": [
      "el",
      "tr",
      "en"
    ]
  },
  {
    "code": "GE",
    "name_en": "Georgia",
    "name_local": "საქართველო",
    "continent": "Asia",
    "languages": [
      "ka",
      "en"
    ]
  },
  {
    "code": "IN",
    "name_en": "India",
    "name_local": "India",
    "continent": "Asia",
    "languages": [
      "hi",
      "en"
    ]
  },
  {
    "code": "ID",
    "name_en": "Indonesia",
    "name_local": "Indonesia",
    "continent": "Asia",
    "languages": [
      "id",
      "en"
    ]
  },
  {
    "code": "IR",
    "name_en": "Iran",
    "name_local": "ایران",
    "continent": "Asia",
    "languages": [
      "fa",
      "en"
    ]
  },
  {
    "code": "IQ",
    "name_en": "Iraq",
    "name_local": "العراق",
    "continent": "Asia",
    "languages": [
      "ar",
      "ku",
      "en"
    ]
  },
  {
    "code": "IL",
    "name_en": "Israel",
    "name_local": "ישראל",
    "continent": "Asia",
    "languages": [
      "he",
      "ar",
      "en"
    ]
  },
  {
    "code": "JP",
    "name_en": "Japan",
    "name_local": "日本",
    "continent": "Asia",
    "languages": [
      "ja",
      "en"
    ]
  },
  {
    "code": "JO",
    "name_en": "Jordan",
    "name_local": "الأردن",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "KZ",
    "name_en": "Kazakhstan",
    "name_local": "Қазақстан",
    "continent": "Asia",
    "languages": [
      "kk",
      "ru",
      "en"
    ]
  },
  {
    "code": "KW",
    "name_en": "Kuwait",
    "name_local": "الكويت",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "KG",
    "name_en": "Kyrgyzstan",
    "name_local": "Кыргызстан",
    "continent": "Asia",
    "languages": [
      "ky",
      "ru",
      "en"
    ]
  },
  {
    "code": "LA",
    "name_en": "Laos",
    "name_local": "ລາວ",
    "continent": "Asia",
    "languages": [
      "lo",
      "en"
    ]
  },
  {
    "code": "LB",
    "name_en": "Lebanon",
    "name_local": "لبنان",
    "continent": "Asia",
    "languages": [
      "ar",
      "fr",
      "en"
    ]
  },
  {
    "code": "MO",
    "name_en": "Macao",
    "name_local": "澳門",
    "continent": "Asia",
    "languages": [
      "zh",
      "pt",
      "en"
    ]
  },
  {
    "code": "MY",
    "name_en": "Malaysia",
    "name_local": "Malaysia",
    "continent": "Asia",
    "languages": [
      "ms",
      "en",
      "zh"
    ]
  },
  {
    "code": "MV",
    "name_en": "Maldives",
    "name_local": "Maldives",
    "continent": "Asia",
    "languages": [
      "dv",
      "en"
    ]
  },
  {
    "code": "MN",
    "name_en": "Mongolia",
    "name_local": "Монгол Улс",
    "continent": "Asia",
    "languages": [
      "mn",
      "en"
    ]
  },
  {
    "code": "MM",
    "name_en": "Myanmar",
    "name_local": "မြန်မာ",
    "continent": "Asia",
    "languages": [
      "my",
      "en"
    ]
  },
  {
    "code": "NP",
    "name_en": "Nepal",
    "name_local": "नेपाल",
    "continent": "Asia",
    "languages": [
      "ne",
      "en"
    ]
  },
  {
    "code": "KP",
    "name_en": "North Korea",
    "name_local": "조선",
    "continent": "Asia",
    "languages": [
      "ko"
    ]
  },
  {
    "code": "OM",
    "name_en": "Oman",
    "name_local": "عُمان",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "PK",
    "name_en": "Pakistan",
    "name_local": "پاکستان",
    "continent": "Asia",
    "languages": [
      "ur",
      "en"
    ]
  },
  {
    "code": "PS",
    "name_en": "Palestine",
    "name_local": "فلسطين",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "PH",
    "name_en": "Philippines",
    "name_local": "Pilipinas",
    "continent": "Asia",
    "languages": [
      "fil",
      "en"
    ]
  },
  {
    "code": "QA",
    "name_en": "Qatar",
    "name_local": "قطر",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "SA",
    "name_en": "Saudi Arabia",
    "name_local": "السعودية",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "SG",
    "name_en": "Singapore",
    "name_local": "Singapore",
    "continent": "Asia",
    "languages": [
      "en",
      "zh",
      "ms",
      "ta"
    ]
  },
  {
    "code": "KR",
    "name_en": "South Korea",
    "name_local": "대한민국",
    "continent": "Asia",
    "languages": [
      "ko",
      "en"
    ]
  },
  {
    "code": "LK",
    "name_en": "Sri Lanka",
    "name_local": "ශ්‍රී ලංකාව",
    "continent": "Asia",
    "languages": [
      "si",
      "ta",
      "en"
    ]
  },
  {
    "code": "SY",
    "name_en": "Syria",
    "name_local": "سوريا",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "TW",
    "name_en": "Taiwan",
    "name_local": "臺灣",
    "continent": "Asia",
    "languages": [
      "zh",
      "en"
    ]
  },
  {
    "code": "TJ",
    "name_en": "Tajikistan",
    "name_local": "Тоҷикистон",
    "continent": "Asia",
    "languages": [
      "tg",
      "ru",
      "en"
    ]
  },
  {
    "code": "TH",
    "name_en": "Thailand",
    "name_local": "ไทย",
    "continent": "Asia",
    "languages": [
      "th",
      "en"
    ]
  },
  {
    "code": "TL",
    "name_en": "Timor-Leste",
    "name_local": "Timor-Leste",
    "continent": "Asia",
    "languages": [
      "pt",
      "tet",
      "en"
    ]
  },
  {
    "code": "TR",
    "name_en": "Turkey",
    "name_local": "Türkiye",
    "continent": "Asia",
    "languages": [
      "tr",
      "en"
    ]
  },
  {
    "code": "TM",
    "name_en": "Turkmenistan",
    "name_local": "Türkmenistan",
    "continent": "Asia",
    "languages": [
      "tk",
      "ru",
      "en"
    ]
  },
  {
    "code": "AE",
    "name_en": "UAE",
    "name_local": "الإمارات",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "UZ",
    "name_en": "Uzbekistan",
    "name_local": "Oʻzbekiston",
    "continent": "Asia",
    "languages": [
      "uz",
      "ru",
      "en"
    ]
  },
  {
    "code": "VN",
    "name_en": "Vietnam",
    "name_local": "Việt Nam",
    "continent": "Asia",
    "languages": [
      "vi",
      "en"
    ]
  },
  {
    "code": "YE",
    "name_en": "Yemen",
    "name_local": "اليمن",
    "continent": "Asia",
    "languages": [
      "ar",
      "en"
    ]
  },
  {
    "code": "AL",
    "name_en": "Albania",
    "name_local": "Shqipëria",
    "continent": "Europe",
    "languages": [
      "sq",
      "en"
    ]
  },
  {
    "code": "AD",
    "name_en": "Andorra",
    "name_local": "Andorra",
    "continent": "Europe",
    "languages": [
      "ca",
      "es",
      "fr",
      "en"
    ]
  },
  {
    "code": "AT",
    "name_en": "Austria",
    "name_local": "Österreich",
    "continent": "Europe",
    "languages": [
      "de",
      "en"
    ]
  },
  {
    "code": "BY",
    "name_en": "Belarus",
    "name_local": "Беларусь",
    "continent": "Europe",
    "languages": [
      "be",
      "ru",
      "en"
    ]
  },
  {
    "code": "BE",
    "name_en": "Belgium",
    "name_local": "België",
    "continent": "Europe",
    "languages": [
      "nl",
      "fr",
      "de",
      "en"
    ]
  },
  {
    "code": "BA",
    "name_en": "Bosnia",
    "name_local": "Bosna i Hercegovina",
    "continent": "Europe",
    "languages": [
      "bs",
      "hr",
      "sr",
      "en"
    ]
  },
  {
    "code": "BG",
    "name_en": "Bulgaria",
    "name_local": "България",
    "continent": "Europe",
    "languages": [
      "bg",
      "en"
    ]
  },
  {
    "code": "HR",
    "name_en": "Croatia",
    "name_local": "Hrvatska",
    "continent": "Europe",
    "languages": [
      "hr",
      "en"
    ]
  },
  {
    "code": "CZ",
    "name_en": "Czech Republic",
    "name_local": "Česko",
    "continent": "Europe",
    "languages": [
      "cs",
      "en"
    ]
  },
  {
    "code": "DK",
    "name_en": "Denmark",
    "name_local": "Danmark",
    "continent": "Europe",
    "languages": [
      "da",
      "en"
    ]
  },
  {
    "code": "EE",
    "name_en": "Estonia",
    "name_local": "Eesti",
    "continent": "Europe",
    "languages": [
      "et",
      "en"
    ]
  },
  {
    "code": "FI",
    "name_en": "Finland",
    "name_local": "Suomi",
    "continent": "Europe",
    "languages": [
      "fi",
      "sv",
      "en"
    ]
  },
  {
    "code": "FR",
    "name_en": "France",
    "name_local": "France",
    "continent": "Europe",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "DE",
    "name_en": "Germany",
    "name_local": "Deutschland",
    "continent": "Europe",
    "languages": [
      "de",
      "en"
    ]
  },
  {
    "code": "GR",
    "name_en": "Greece",
    "name_local": "Ελλάδα",
    "continent": "Europe",
    "languages": [
      "el",
      "en"
    ]
  },
  {
    "code": "HU",
    "name_en": "Hungary",
    "name_local": "Magyarország",
    "continent": "Europe",
    "languages": [
      "hu",
      "en"
    ]
  },
  {
    "code": "IS",
    "name_en": "Iceland",
    "name_local": "Ísland",
    "continent": "Europe",
    "languages": [
      "is",
      "en"
    ]
  },
  {
    "code": "IE",
    "name_en": "Ireland",
    "name_local": "Éire",
    "continent": "Europe",
    "languages": [
      "en",
      "ga"
    ]
  },
  {
    "code": "IT",
    "name_en": "Italy",
    "name_local": "Italia",
    "continent": "Europe",
    "languages": [
      "it",
      "en"
    ]
  },
  {
    "code": "XK",
    "name_en": "Kosovo",
    "name_local": "Kosovë",
    "continent": "Europe",
    "languages": [
      "sq",
      "sr",
      "en"
    ]
  },
  {
    "code": "LV",
    "name_en": "Latvia",
    "name_local": "Latvija",
    "continent": "Europe",
    "languages": [
      "lv",
      "en"
    ]
  },
  {
    "code": "LI",
    "name_en": "Liechtenstein",
    "name_local": "Liechtenstein",
    "continent": "Europe",
    "languages": [
      "de",
      "en"
    ]
  },
  {
    "code": "LT",
    "name_en": "Lithuania",
    "name_local": "Lietuva",
    "continent": "Europe",
    "languages": [
      "lt",
      "en"
    ]
  },
  {
    "code": "LU",
    "name_en": "Luxembourg",
    "name_local": "Lëtzebuerg",
    "continent": "Europe",
    "languages": [
      "lb",
      "fr",
      "de",
      "en"
    ]
  },
  {
    "code": "MT",
    "name_en": "Malta",
    "name_local": "Malta",
    "continent": "Europe",
    "languages": [
      "mt",
      "en"
    ]
  },
  {
    "code": "MD",
    "name_en": "Moldova",
    "name_local": "Moldova",
    "continent": "Europe",
    "languages": [
      "ro",
      "ru",
      "en"
    ]
  },
  {
    "code": "MC",
    "name_en": "Monaco",
    "name_local": "Monaco",
    "continent": "Europe",
    "languages": [
      "fr",
      "en"
    ]
  },
  {
    "code": "ME",
    "name_en": "Montenegro",
    "name_local": "Crna Gora",
    "continent": "Europe",
    "languages": [
      "sr",
      "me",
      "bs",
      "hr",
      "sq"
    ]
  },
  {
    "code": "NL",
    "name_en": "Netherlands",
    "name_local": "Nederland",
    "continent": "Europe",
    "languages": [
      "nl",
      "en"
    ]
  },
  {
    "code": "MK",
    "name_en": "North Macedonia",
    "name_local": "Северна Македонија",
    "continent": "Europe",
    "languages": [
      "mk",
      "sq",
      "en"
    ]
  },
  {
    "code": "NO",
    "name_en": "Norway",
    "name_local": "Norge",
    "continent": "Europe",
    "languages": [
      "no",
      "en"
    ]
  },
  {
    "code": "PL",
    "name_en": "Poland",
    "name_local": "Polska",
    "continent": "Europe",
    "languages": [
      "pl",
      "en"
    ]
  },
  {
    "code": "PT",
    "name_en": "Portugal",
    "name_local": "Portugal",
    "continent": "Europe",
    "languages": [
      "pt",
      "en"
    ]
  },
  {
    "code": "RO",
    "name_en": "Romania",
    "name_local": "România",
    "continent": "Europe",
    "languages": [
      "ro",
      "en"
    ]
  },
  {
    "code": "RU",
    "name_en": "Russia",
    "name_local": "Россия",
    "continent": "Europe",
    "languages": [
      "ru",
      "en"
    ]
  },
  {
    "code": "SM",
    "name_en": "San Marino",
    "name_local": "San Marino",
    "continent": "Europe",
    "languages": [
      "it",
      "en"
    ]
  },
  {
    "code": "RS",
    "name_en": "Serbia",
    "name_local": "Srbija",
    "continent": "Europe",
    "languages": [
      "sr",
      "en"
    ]
  },
  {
    "code": "SK",
    "name_en": "Slovakia",
    "name_local": "Slovensko",
    "continent": "Europe",
    "languages": [
      "sk",
      "en"
    ]
  },
  {
    "code": "SI",
    "name_en": "Slovenia",
    "name_local": "Slovenija",
    "continent": "Europe",
    "languages": [
      "sl",
      "en"
    ]
  },
  {
    "code": "ES",
    "name_en": "Spain",
    "name_local": "España",
    "continent": "Europe",
    "languages": [
      "es",
      "ca",
      "gl",
      "eu",
      "en"
    ]
  },
  {
    "code": "SE",
    "name_en": "Sweden",
    "name_local": "Sverige",
    "continent": "Europe",
    "languages": [
      "sv",
      "en"
    ]
  },
  {
    "code": "CH",
    "name_en": "Switzerland",
    "name_local": "Schweiz",
    "continent": "Europe",
    "languages": [
      "de",
      "fr",
      "it",
      "rm",
      "en"
    ]
  },
  {
    "code": "UA",
    "name_en": "Ukraine",
    "name_local": "Україна",
    "continent": "Europe",
    "languages": [
      "uk",
      "en"
    ]
  },
  {
    "code": "GB",
    "name_en": "UK",
    "name_local": "United Kingdom",
    "continent": "Europe",
    "languages": [
      "en",
      "cy",
      "gd"
    ]
  },
  {
    "code": "VA",
    "name_en": "Vatican",
    "name_local": "Vaticano",
    "continent": "Europe",
    "languages": [
      "it",
      "la",
      "en"
    ]
  },
  {
    "code": "AG",
    "name_en": "Antigua and Barbuda",
    "name_local": "Antigua and Barbuda",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "BS",
    "name_en": "Bahamas",
    "name_local": "Bahamas",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "BB",
    "name_en": "Barbados",
    "name_local": "Barbados",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "BZ",
    "name_en": "Belize",
    "name_local": "Belize",
    "continent": "North America",
    "languages": [
      "en",
      "es"
    ]
  },
  {
    "code": "CA",
    "name_en": "Canada",
    "name_local": "Canada",
    "continent": "North America",
    "languages": [
      "en",
      "fr"
    ]
  },
  {
    "code": "CR",
    "name_en": "Costa Rica",
    "name_local": "Costa Rica",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "CU",
    "name_en": "Cuba",
    "name_local": "Cuba",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "DM",
    "name_en": "Dominica",
    "name_local": "Dominica",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "DO",
    "name_en": "Dominican Republic",
    "name_local": "República Dominicana",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "SV",
    "name_en": "El Salvador",
    "name_local": "El Salvador",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "GD",
    "name_en": "Grenada",
    "name_local": "Grenada",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "GT",
    "name_en": "Guatemala",
    "name_local": "Guatemala",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "HT",
    "name_en": "Haiti",
    "name_local": "Haïti",
    "continent": "North America",
    "languages": [
      "fr",
      "ht",
      "en"
    ]
  },
  {
    "code": "HN",
    "name_en": "Honduras",
    "name_local": "Honduras",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "JM",
    "name_en": "Jamaica",
    "name_local": "Jamaica",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "MX",
    "name_en": "Mexico",
    "name_local": "México",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "NI",
    "name_en": "Nicaragua",
    "name_local": "Nicaragua",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "PA",
    "name_en": "Panama",
    "name_local": "Panamá",
    "continent": "North America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "KN",
    "name_en": "Saint Kitts and Nevis",
    "name_local": "Saint Kitts and Nevis",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "LC",
    "name_en": "Saint Lucia",
    "name_local": "Saint Lucia",
    "continent": "North America",
    "languages": [
      "en",
      "fr"
    ]
  },
  {
    "code": "VC",
    "name_en": "Saint Vincent",
    "name_local": "Saint Vincent and the Grenadines",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "TT",
    "name_en": "Trinidad and Tobago",
    "name_local": "Trinidad and Tobago",
    "continent": "North America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "US",
    "name_en": "USA",
    "name_local": "United States",
    "continent": "North America",
    "languages": [
      "en",
      "es"
    ]
  },
  {
    "code": "AR",
    "name_en": "Argentina",
    "name_local": "Argentina",
    "continent": "South America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "BO",
    "name_en": "Bolivia",
    "name_local": "Bolivia",
    "continent": "South America",
    "languages": [
      "es",
      "qu",
      "ay",
      "gn"
    ]
  },
  {
    "code": "BR",
    "name_en": "Brazil",
    "name_local": "Brasil",
    "continent": "South America",
    "languages": [
      "pt",
      "en"
    ]
  },
  {
    "code": "CL",
    "name_en": "Chile",
    "name_local": "Chile",
    "continent": "South America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "CO",
    "name_en": "Colombia",
    "name_local": "Colombia",
    "continent": "South America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "EC",
    "name_en": "Ecuador",
    "name_local": "Ecuador",
    "continent": "South America",
    "languages": [
      "es",
      "qu",
      "en"
    ]
  },
  {
    "code": "GY",
    "name_en": "Guyana",
    "name_local": "Guyana",
    "continent": "South America",
    "languages": [
      "en"
    ]
  },
  {
    "code": "PY",
    "name_en": "Paraguay",
    "name_local": "Paraguay",
    "continent": "South America",
    "languages": [
      "es",
      "gn",
      "en"
    ]
  },
  {
    "code": "PE",
    "name_en": "Peru",
    "name_local": "Perú",
    "continent": "South America",
    "languages": [
      "es",
      "qu",
      "ay",
      "en"
    ]
  },
  {
    "code": "SR",
    "name_en": "Suriname",
    "name_local": "Suriname",
    "continent": "South America",
    "languages": [
      "nl",
      "en"
    ]
  },
  {
    "code": "UY",
    "name_en": "Uruguay",
    "name_local": "Uruguay",
    "continent": "South America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "VE",
    "name_en": "Venezuela",
    "name_local": "Venezuela",
    "continent": "South America",
    "languages": [
      "es",
      "en"
    ]
  },
  {
    "code": "AU",
    "name_en": "Australia",
    "name_local": "Australia",
    "continent": "Oceania",
    "languages": [
      "en"
    ]
  },
  {
    "code": "FJ",
    "name_en": "Fiji",
    "name_local": "Fiji",
    "continent": "Oceania",
    "languages": [
      "en",
      "fj",
      "hi"
    ]
  },
  {
    "code": "KI",
    "name_en": "Kiribati",
    "name_local": "Kiribati",
    "continent": "Oceania",
    "languages": [
      "en",
      "gil"
    ]
  },
  {
    "code": "MH",
    "name_en": "Marshall Islands",
    "name_local": "Aorōkin M̧ajeļ",
    "continent": "Oceania",
    "languages": [
      "en",
      "mh"
    ]
  },
  {
    "code": "FM",
    "name_en": "Micronesia",
    "name_local": "Micronesia",
    "continent": "Oceania",
    "languages": [
      "en"
    ]
  },
  {
    "code": "NR",
    "name_en": "Nauru",
    "name_local": "Nauru",
    "continent": "Oceania",
    "languages": [
      "en",
      "na"
    ]
  },
  {
    "code": "NZ",
    "name_en": "New Zealand",
    "name_local": "New Zealand",
    "continent": "Oceania",
    "languages": [
      "en",
      "mi"
    ]
  },
  {
    "code": "PW",
    "name_en": "Palau",
    "name_local": "Belau",
    "continent": "Oceania",
    "languages": [
      "en",
      "pau"
    ]
  },
  {
    "code": "PG",
    "name_en": "Papua New Guinea",
    "name_local": "Papua New Guinea",
    "continent": "Oceania",
    "languages": [
      "en",
      "tpi",
      "ho"
    ]
  },
  {
    "code": "WS",
    "name_en": "Samoa",
    "name_local": "Samoa",
    "continent": "Oceania",
    "languages": [
      "sm",
      "en"
    ]
  },
  {
    "code": "SB",
    "name_en": "Solomon Islands",
    "name_local": "Solomon Islands",
    "continent": "Oceania",
    "languages": [
      "en"
    ]
  },
  {
    "code": "TO",
    "name_en": "Tonga",
    "name_local": "Tonga",
    "continent": "Oceania",
    "languages": [
      "to",
      "en"
    ]
  },
  {
    "code": "TV",
    "name_en": "Tuvalu",
    "name_local": "Tuvalu",
    "continent": "Oceania",
    "languages": [
      "en",
      "tvl"
    ]
  },
  {
    "code": "VU",
    "name_en": "Vanuatu",
    "name_local": "Vanuatu",
    "continent": "Oceania",
    "languages": [
      "bi",
      "en",
      "fr"
    ]
  }
];


const COUNTRY_ZH_BY_CODE: Record<string, string> = {
  CN: "中国", IN: "印度", DE: "德国", US: "美国", GB: "英国", FR: "法国", JP: "日本", KR: "韩国",
  BR: "巴西", RU: "俄罗斯", CA: "加拿大", AU: "澳大利亚", IT: "意大利", ES: "西班牙", MX: "墨西哥",
  ZA: "南非", NG: "尼日利亚", EG: "埃及", TR: "土耳其", SA: "沙特阿拉伯", AE: "阿联酋", ID: "印度尼西亚",
  PK: "巴基斯坦", BD: "孟加拉国", VN: "越南", TH: "泰国", MY: "马来西亚", SG: "新加坡", PH: "菲律宾",
  NZ: "新西兰", AR: "阿根廷", CL: "智利", CO: "哥伦比亚", PE: "秘鲁", NL: "荷兰", BE: "比利时",
  SE: "瑞典", NO: "挪威", DK: "丹麦", FI: "芬兰", PL: "波兰", CH: "瑞士", AT: "奥地利", IE: "爱尔兰",
  PT: "葡萄牙", CZ: "捷克", HU: "匈牙利", RO: "罗马尼亚", GR: "希腊", UA: "乌克兰", IL: "以色列",
  IR: "伊朗", IQ: "伊拉克", QA: "卡塔尔", KW: "科威特", OM: "阿曼", JO: "约旦", LK: "斯里兰卡",
  NP: "尼泊尔", MM: "缅甸", KH: "柬埔寨", LA: "老挝", MN: "蒙古", KZ: "哈萨克斯坦", UZ: "乌兹别克斯坦",
  ET: "埃塞俄比亚", KE: "肯尼亚", TZ: "坦桑尼亚", UG: "乌干达", GH: "加纳", CI: "科特迪瓦", MA: "摩洛哥",
  DZ: "阿尔及利亚", TN: "突尼斯", LY: "利比亚", SD: "苏丹", CM: "喀麦隆", ZM: "赞比亚", ZW: "津巴布韦"
};

export const geoData: GeoEntry[] = rawGeoData.map((entry) => ({
  ...entry,
  name_zh: COUNTRY_ZH_BY_CODE[entry.code] ?? entry.name_local ?? entry.name_en,
}));
