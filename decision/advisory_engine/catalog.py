"""Multilingual advisory templates.

Real translated advisory strings per (AQI band, audience, language). This is
the extensible catalog: adding a language means adding a locale block; adding an
audience means adding a key. Bundled languages: en, hi, mr, ta, bn, te.

Templates use {location} and {aqi} placeholders. Bands are collapsed to three
operational tiers (safe / caution / danger) to keep the catalog maintainable
while covering the full CPCB scale.
"""
from __future__ import annotations

# Tier mapping from CPCB band -> advisory tier
BAND_TIER = {
    "Good": "safe",
    "Satisfactory": "safe",
    "Moderate": "caution",
    "Poor": "caution",
    "Very Poor": "danger",
    "Severe": "danger",
    "Severe+": "danger",
}

# catalog[lang][audience][tier] -> {headline, message, actions[]}
CATALOG: dict[str, dict[str, dict[str, dict]]] = {
    "en": {
        "citizen": {
            "safe": {
                "headline": "Air quality is acceptable in {location}",
                "message": "AQI is {aqi}. Air quality is satisfactory for most people.",
                "actions": ["Enjoy normal outdoor activity.",
                            "Sensitive individuals should stay aware of any symptoms."],
            },
            "caution": {
                "headline": "Reduce prolonged outdoor exertion in {location}",
                "message": "AQI is {aqi}. Sensitive groups may feel breathing discomfort.",
                "actions": ["Limit prolonged or heavy outdoor exertion.",
                            "Keep windows closed during peak traffic hours.",
                            "Sensitive individuals should carry medication."],
            },
            "danger": {
                "headline": "Avoid outdoor activity in {location}",
                "message": "AQI is {aqi}. Air quality is hazardous.",
                "actions": ["Avoid all outdoor physical activity.",
                            "Wear an N95 mask if you must go outside.",
                            "Use air purifiers indoors and keep windows shut."],
            },
        },
        "hospital": {
            "safe": {
                "headline": "Routine operations — {location}",
                "message": "AQI is {aqi}. No air-quality surge expected.",
                "actions": ["Maintain routine respiratory-care readiness."],
            },
            "caution": {
                "headline": "Prepare for respiratory cases — {location}",
                "message": "AQI is {aqi}. Expect a rise in respiratory complaints.",
                "actions": ["Stock nebulisers and inhalers.",
                            "Brief triage staff on pollution-related symptoms."],
            },
            "danger": {
                "headline": "Activate surge protocol — {location}",
                "message": "AQI is {aqi}. Expect increased respiratory and cardiac admissions.",
                "actions": ["Ensure adequate oxygen and nebuliser stock.",
                            "Prepare additional beds for respiratory emergencies.",
                            "Coordinate with authorities on capacity."],
            },
        },
        "school": {
            "safe": {
                "headline": "Normal school activity — {location}",
                "message": "AQI is {aqi}. Outdoor activities can proceed.",
                "actions": ["Proceed with outdoor sports and assemblies."],
            },
            "caution": {
                "headline": "Limit outdoor sports — {location}",
                "message": "AQI is {aqi}. Reduce strenuous outdoor activity for children.",
                "actions": ["Shorten outdoor sports and assemblies.",
                            "Watch children with asthma closely."],
            },
            "danger": {
                "headline": "Suspend outdoor activity — {location}",
                "message": "AQI is {aqi}. Keep children indoors.",
                "actions": ["Suspend all outdoor sports and assemblies.",
                            "Consider hybrid or online classes as advised by authorities.",
                            "Keep classroom windows closed."],
            },
        },
        "outdoor_worker": {
            "safe": {
                "headline": "Normal outdoor work — {location}",
                "message": "AQI is {aqi}. Standard precautions apply.",
                "actions": ["Stay hydrated; take normal breaks."],
            },
            "caution": {
                "headline": "Take extra breaks — {location}",
                "message": "AQI is {aqi}. Prolonged exposure may cause discomfort.",
                "actions": ["Take frequent breaks in cleaner air.",
                            "Use a mask during dusty tasks."],
            },
            "danger": {
                "headline": "Minimise outdoor exposure — {location}",
                "message": "AQI is {aqi}. Continuous outdoor work is unsafe.",
                "actions": ["Wear an N95 mask at all times outdoors.",
                            "Rotate shifts to limit continuous exposure.",
                            "Reschedule strenuous work to lower-pollution hours."],
            },
        },
        "senior_citizen": {
            "safe": {
                "headline": "Air is fine for a walk — {location}",
                "message": "AQI is {aqi}. Comfortable for outdoor activity.",
                "actions": ["Enjoy a walk; carry any regular medication."],
            },
            "caution": {
                "headline": "Take it easy outdoors — {location}",
                "message": "AQI is {aqi}. You may feel breathing discomfort.",
                "actions": ["Limit time outdoors.",
                            "Keep prescribed inhalers handy."],
            },
            "danger": {
                "headline": "Stay indoors — {location}",
                "message": "AQI is {aqi}. Outdoor air is hazardous for you.",
                "actions": ["Remain indoors with windows closed.",
                            "Use an air purifier if available.",
                            "Seek medical help if you feel breathless."],
            },
        },
    },
}


# ---- Regional-language catalogs (citizen + shared audiences) --------------
# Each locale provides headline/message/action strings. Audiences that are not
# separately translated fall back to the citizen block of the same language,
# then to English — handled by the engine.
CATALOG["hi"] = {
    "citizen": {
        "safe": {
            "headline": "{location} में वायु गुणवत्ता ठीक है",
            "message": "AQI {aqi} है। हवा अधिकांश लोगों के लिए संतोषजनक है।",
            "actions": ["सामान्य बाहरी गतिविधि करें।",
                        "संवेदनशील लोग लक्षणों पर ध्यान दें।"],
        },
        "caution": {
            "headline": "{location} में लंबे समय तक बाहर मेहनत कम करें",
            "message": "AQI {aqi} है। संवेदनशील लोगों को सांस में तकलीफ हो सकती है।",
            "actions": ["लंबी या भारी बाहरी मेहनत सीमित करें।",
                        "व्यस्त समय में खिड़कियाँ बंद रखें।",
                        "संवेदनशील लोग दवा साथ रखें।"],
        },
        "danger": {
            "headline": "{location} में बाहरी गतिविधि से बचें",
            "message": "AQI {aqi} है। हवा हानिकारक है।",
            "actions": ["सभी बाहरी शारीरिक गतिविधि से बचें।",
                        "बाहर जाना ज़रूरी हो तो N95 मास्क पहनें।",
                        "घर के अंदर एयर प्यूरीफायर चलाएँ, खिड़कियाँ बंद रखें।"],
        },
    },
}
CATALOG["mr"] = {
    "citizen": {
        "safe": {
            "headline": "{location} मध्ये हवेची गुणवत्ता ठीक आहे",
            "message": "AQI {aqi} आहे. हवा बहुतेकांसाठी समाधानकारक आहे.",
            "actions": ["नेहमीप्रमाणे बाहेरील कामे करा.",
                        "संवेदनशील व्यक्तींनी लक्षणांकडे लक्ष द्यावे."],
        },
        "caution": {
            "headline": "{location} मध्ये दीर्घ बाहेरील श्रम कमी करा",
            "message": "AQI {aqi} आहे. संवेदनशील लोकांना श्वासाचा त्रास होऊ शकतो.",
            "actions": ["दीर्घ किंवा जड बाहेरील श्रम मर्यादित करा.",
                        "गर्दीच्या वेळेत खिडक्या बंद ठेवा."],
        },
        "danger": {
            "headline": "{location} मध्ये बाहेरील हालचाल टाळा",
            "message": "AQI {aqi} आहे. हवा घातक आहे.",
            "actions": ["सर्व बाहेरील शारीरिक हालचाल टाळा.",
                        "बाहेर जाणे आवश्यक असल्यास N95 मास्क वापरा.",
                        "घरात एअर प्युरिफायर वापरा, खिडक्या बंद ठेवा."],
        },
    },
}
CATALOG["ta"] = {
    "citizen": {
        "safe": {
            "headline": "{location} இல் காற்றின் தரம் நல்லது",
            "message": "AQI {aqi}. காற்று பெரும்பாலானோருக்கு திருப்திகரமானது.",
            "actions": ["வழக்கமான வெளிப்புற செயல்பாடுகளைச் செய்யலாம்.",
                        "உணர்திறன் உள்ளவர்கள் அறிகுறிகளைக் கவனிக்கவும்."],
        },
        "caution": {
            "headline": "{location} இல் நீண்ட வெளிப்புற உழைப்பைக் குறைக்கவும்",
            "message": "AQI {aqi}. உணர்திறன் உள்ளவர்களுக்கு மூச்சுத் திணறல் ஏற்படலாம்.",
            "actions": ["நீண்ட அல்லது கடுமையான வெளிப்புற உழைப்பைக் கட்டுப்படுத்தவும்.",
                        "நெரிசல் நேரத்தில் ஜன்னல்களை மூடி வைக்கவும்."],
        },
        "danger": {
            "headline": "{location} இல் வெளிப்புற செயல்பாட்டைத் தவிர்க்கவும்",
            "message": "AQI {aqi}. காற்று ஆபத்தானது.",
            "actions": ["அனைத்து வெளிப்புற உடல் செயல்பாடுகளையும் தவிர்க்கவும்.",
                        "வெளியே செல்ல வேண்டுமானால் N95 முகக்கவசம் அணியவும்.",
                        "வீட்டில் காற்று சுத்திகரிப்பானைப் பயன்படுத்தவும்."],
        },
    },
}
CATALOG["bn"] = {
    "citizen": {
        "safe": {
            "headline": "{location}-এ বাতাসের মান ঠিক আছে",
            "message": "AQI {aqi}। বাতাস বেশিরভাগ মানুষের জন্য সন্তোষজনক।",
            "actions": ["স্বাভাবিক বাইরের কার্যকলাপ করুন।",
                        "সংবেদনশীল ব্যক্তিরা লক্ষণ খেয়াল রাখুন।"],
        },
        "caution": {
            "headline": "{location}-এ দীর্ঘ বাইরের পরিশ্রম কমান",
            "message": "AQI {aqi}। সংবেদনশীলদের শ্বাসকষ্ট হতে পারে।",
            "actions": ["দীর্ঘ বা ভারী বাইরের পরিশ্রম সীমিত করুন।",
                        "ব্যস্ত সময়ে জানালা বন্ধ রাখুন।"],
        },
        "danger": {
            "headline": "{location}-এ বাইরের কার্যকলাপ এড়িয়ে চলুন",
            "message": "AQI {aqi}। বাতাস ক্ষতিকর।",
            "actions": ["সমস্ত বাইরের শারীরিক কার্যকলাপ এড়িয়ে চলুন।",
                        "বাইরে যেতে হলে N95 মাস্ক পরুন।",
                        "ঘরে এয়ার পিউরিফায়ার ব্যবহার করুন, জানালা বন্ধ রাখুন।"],
        },
    },
}
CATALOG["te"] = {
    "citizen": {
        "safe": {
            "headline": "{location}లో గాలి నాణ్యత బాగుంది",
            "message": "AQI {aqi}. గాలి చాలామందికి సంతృప్తికరంగా ఉంది.",
            "actions": ["సాధారణ బహిరంగ కార్యకలాపాలు చేయవచ్చు.",
                        "సున్నితమైన వ్యక్తులు లక్షణాలను గమనించండి."],
        },
        "caution": {
            "headline": "{location}లో ఎక్కువసేపు బహిరంగ శ్రమ తగ్గించండి",
            "message": "AQI {aqi}. సున్నితమైన వారికి శ్వాస ఇబ్బంది కలగవచ్చు.",
            "actions": ["ఎక్కువసేపు లేదా భారీ బహిరంగ శ్రమను పరిమితం చేయండి.",
                        "రద్దీ సమయంలో కిటికీలు మూసి ఉంచండి."],
        },
        "danger": {
            "headline": "{location}లో బహిరంగ కార్యకలాపాలను నివారించండి",
            "message": "AQI {aqi}. గాలి ప్రమాదకరం.",
            "actions": ["అన్ని బహిరంగ శారీరక కార్యకలాపాలను నివారించండి.",
                        "బయటకు వెళ్లాల్సి వస్తే N95 మాస్క్ ధరించండి.",
                        "ఇంట్లో ఎయిర్ ప్యూరిఫైయర్ వాడండి, కిటికీలు మూసి ఉంచండి."],
        },
    },
}

SUPPORTED = list(CATALOG.keys())
