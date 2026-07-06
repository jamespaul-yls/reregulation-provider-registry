from enum import StrEnum


class ProgramType(StrEnum):
    abs = "abs"
    sandbox = "sandbox"
    alp_license = "alp_license"
    paraprofessional_pilot = "paraprofessional_pilot"
    community_justice_worker = "community_justice_worker"
    document_preparer = "document_preparer"


class ProgramStatus(StrEnum):
    active = "active"
    sunset = "sunset"
    proposed = "proposed"
    paused = "paused"


class ProviderType(StrEnum):
    entity = "entity"
    individual = "individual"


class CurrentStatus(StrEnum):
    active = "active"
    exited = "exited"
    suspended = "suspended"
    revoked = "revoked"
    unknown = "unknown"


class EventType(StrEnum):
    authorized = "authorized"
    status_change = "status_change"
    disappeared_from_roster = "disappeared_from_roster"
    disciplined = "disciplined"
    reinstated = "reinstated"


class AliasSource(StrEnum):
    roster = "roster"
    website = "website"
    litigation = "litigation"
    manual = "manual"


class MediaType(StrEnum):
    html = "html"
    pdf = "pdf"
    json = "json"
    xlsx = "xlsx"


class MatchMethod(StrEnum):
    exact = "exact"
    fuzzy = "fuzzy"
    manual = "manual"
