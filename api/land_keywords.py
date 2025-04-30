def is_land_related_english(text):
    """Checks if the given text (in English) contains core land-related keywords."""
    english_land_keywords_core = [
        "land", "survey", "boundary", "property", "real estate", "title", "zoning",
        "parcel", "lot", "terrain", "geodetic", "topography", "easement", "tenure",
        "subdivision", "appraisal", "mortgage", "cadastral", "geospatial", "dispute",
        "land use", "notary", "affidavit", "forestry", "conservation", "mapping",
        "site development", "land development", "land acquisition", "land leasing",
        "tax", "blueprint", "permit", "claim", "reform", "condominium", "townhouse",
        "commercial", "agricultural", "industrial", "residential", "management",
        "administration", "policy", "law", "information system", "rights",
        "transactions", "agreement", "payment", "verification", "investigation",
        "settlement", "mediation", "arbitration", "litigation", "settlers", "housing",
        "price", "market", "investment", "buy", "sell", "construction", "mining",
        "tourism", "environmental protection", "preservation", "rehabilitation",
        "reclassification", "consolidation", "division", "exchange", "donation",
        "inheritance", "distribution", "planning", "ordinance", "code", "regulations",
        "infrastructure", "public access", "private", "public", "heritage",
        "ancestral domain", "indigenous", "governance", "economics", "instruments"
    ]
    lowered_text = text.lower()
    return any(keyword in lowered_text for keyword in english_land_keywords_core)

def is_land_related_bisaya(text):
    """Checks if the given text (in Bisaya) contains core land-related keywords."""
    bisaya_land_keywords_core = [
        "yuta", "sukod", "utlanan", "propyedad", "real estate", "titulo", "zoning",
        "parsela", "lote", "tereyn", "geodetic", "topograpiya", "easement", "tenure",
        "subdibisyon", "appraisal", "mortgage", "kadastral", "geospatial", "panagbangi",
        "gamit sa yuta", "notaryo", "affidavit", "lasang", "konserbasyon", "mapping",
        "site development", "pagpalambo sa yuta", "pag-angkon sa yuta", "pag-abang sa yuta",
        "buhis", "plano", "permiso", "claim", "reporma", "condominium", "townhouse",
        "komersyal", "agrikultural", "industriyal", "residensyal", "pagdumala",
        "administrasyon", "polisya", "balaod", "sistema sa impormasyon", "katungod",
        "transaksyon", "kasabutan", "pagbayad", "beripikasyon", "imbestigasyon",
        "areglo", "mediasyon", "arbitrasyon", "litigasyon", "settler", "pabahay",
        "presyo", "merkado", "puhunan", "palit", "baligya", "konstruksyon", "mina",
        "turismo", "proteksyon sa kinaiyahan", "preserbasyon", "rehabilitasyon",
        "reklasipikasyon", "konsolidasyon", "dibisyon", "ilis", "donasyon",
        "kabilin", "apod-apod", "pagplano", "ordinansa", "kodigo", "regulasyon",
        "imprastraktura", "publikong access", "pribado", "publiko", "kabilin",
        "ancestral domain", "lumad", "pagdumala", "ekonomiya", "instrumento"
    ]
    lowered_text = text.lower()
    return any(keyword in lowered_text for keyword in bisaya_land_keywords_core)