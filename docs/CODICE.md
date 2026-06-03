# Estándar CODICE — estructura y campos

CODICE (COntratos y licitaciones en formato Digital para Intercambio y Compartición de información entre Entidades) es el estándar XML que usa la Plataforma de Contratación del Sector Público (PLACSP) para publicar los datos de contratación. Los feeds que expone son ficheros ATOM donde cada `<entry>` lleva un bloque CODICE con los datos del expediente.

## Namespaces

```xml
atom:          http://www.w3.org/2005/Atom
cac:           urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2
cbc:           urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2
cac-place-ext: urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2
cbc-place-ext: urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2
```

`cac`/`cbc` son componentes estándar UBL (Universal Business Language). Los prefijos `*-place-ext` son extensiones españolas de la DGPE (Dirección General del Patrimonio del Estado).

---

## Metadatos del feed ATOM

Cada `<entry>` del fichero ATOM incluye estos metadatos independientes del bloque CODICE:

| Elemento | Descripción |
|----------|-------------|
| `atom:id` | URI único del entry en el feed. Identifica la publicación, no el expediente. |
| `atom:title` | Título del expediente tal como lo publica el órgano. |
| `atom:summary` | Resumen corto del objeto del contrato. |
| `atom:updated` | Fecha y hora de la última actualización de este entry en el feed. |
| `atom:link @href` | Enlace directo a la ficha del expediente en PLACSP. |

---

## Licitaciones y contratos menores

Ambos tipos usan `cac-place-ext:ContractFolderStatus` como raíz. Los contratos menores no incluyen lotes ni criterios de adjudicación.

```
atom:entry
└── cac-place-ext:ContractFolderStatus
    ├── cbc:ContractFolderID                          número de expediente
    ├── cbc-place-ext:ContractFolderStatusCode        estado del expediente
    │
    ├── cac-place-ext:LocatedContractingParty         órgano contratante
    │   ├── cbc:ContractingPartyTypeCode              tipo de administración
    │   ├── cbc:ActivityCode                          actividad principal (puede repetirse)
    │   ├── cbc:BuyerProfileURIID                     URL del perfil del contratante
    │   └── cac:Party
    │       ├── cac:PartyIdentification               puede repetirse con distintos schemeName
    │       │   └── cbc:ID  @schemeName               NIF | DIR3 | ID_PLATAFORMA
    │       ├── cac:PartyName/cbc:Name
    │       ├── cac:PostalAddress
    │       │   ├── cbc:CityName
    │       │   ├── cbc:PostalZone
    │       │   ├── cac:AddressLine/cbc:Line
    │       │   └── cac:Country/cbc:IdentificationCode
    │       └── cac:Contact
    │           ├── cbc:Name
    │           ├── cbc:Telephone
    │           ├── cbc:Telefax
    │           └── cbc:ElectronicMail
    │   (cac-place-ext:ParentLocatedParty anidado — jerarquía del órgano)
    │
    ├── cac:ProcurementProject                        objeto del contrato
    │   ├── cbc:Name                                  descripción del objeto
    │   ├── cbc:Description
    │   ├── cbc:TypeCode                              tipo de contrato
    │   ├── cbc:SubTypeCode                           subtipo según clasificación DGPE
    │   ├── cbc:EstimatedOverallContractAmount        valor estimado (incluye prórrogas y opciones)
    │   ├── cac:BudgetAmount
    │   │   ├── cbc:TaxExclusiveAmount  @currencyID   presupuesto base sin IVA
    │   │   └── cbc:TotalAmount                       presupuesto base con IVA
    │   ├── cac:RequiredCommodityClassification       puede repetirse por contrato
    │   │   └── cbc:ItemClassificationCode            código CPV
    │   ├── cac:RealizedLocation
    │   │   ├── cbc:CountrySubentity                  nombre de la CCAA o provincia
    │   │   ├── cbc:CountrySubentityCode              código NUTS
    │   │   └── cac:Address/cac:Country/cbc:IdentificationCode
    │   └── cac:PlannedPeriod
    │       ├── cbc:DurationMeasure  @unitCode         duración numérica (MON=meses, DAY=días)
    │       ├── cbc:StartDate
    │       └── cbc:EndDate
    │
    ├── cac:TenderResult                              resultado de adjudicación
    │   ├── cbc:ResultCode                            código del resultado
    │   ├── cbc:AwardDate                             fecha de adjudicación
    │   ├── cbc:ReceivedDate                          fecha de formalización del contrato
    │   ├── cbc:ReceivedTenderQuantity                número de ofertas recibidas
    │   ├── cbc:SMEAwardedIndicator                   true si el adjudicatario es PYME
    │   ├── cac:WinningParty
    │   │   ├── cac:PartyIdentification/cbc:ID  @schemeName   NIF para empresas españolas; otros esquemas para extranjeras
    │   │   ├── cac:PartyName/cbc:Name
    │   │   └── cac:PhysicalLocation/cac:Address/cac:Country/cbc:IdentificationCode
    │   └── cac:AwardedTenderedProject
    │       └── cac:LegalMonetaryTotal
    │           ├── cbc:TaxExclusiveAmount            importe adjudicado sin IVA
    │           └── cbc:PayableAmount                 importe adjudicado con IVA
    │
    ├── cac:TenderingProcess                         proceso de licitación
    │   ├── cbc:ProcedureCode                        tipo de procedimiento
    │   ├── cbc:UrgencyCode                          código de urgencia
    │   ├── cac:TenderSubmissionDeadlinePeriod
    │   │   ├── cbc:EndDate                          fecha límite de presentación
    │   │   └── cbc:EndTime                          hora límite de presentación
    │   └── cac:OpenTenderEvent
    │       ├── cbc:OccurrenceDate                   fecha de apertura de plicas
    │       ├── cbc:OccurrenceTime
    │       └── cbc:Description
    │
    ├── cac:TenderingTerms                           condiciones de licitación
    │   ├── cbc:FundingProgramCode  @name            código y nombre del programa de financiación
    │   └── cbc:RequiredFinancialGuarantee           si se exige garantía definitiva
    │
    ├── cac-place-ext:ValidNoticeInfo                información de publicación
    │   ├── cbc-place-ext:NoticeTypeCode             tipo de anuncio
    │   └── cac-place-ext:AdditionalPublicationStatus
    │       ├── cbc-place-ext:PublicationMediaName   medio de publicación
    │       └── cac-place-ext:AdditionalPublicationDocumentReference
    │           └── cbc:IssueDate                    fecha de publicación en ese medio
    │
    ├── cac:ProcurementProjectLot                    (solo licitaciones, puede repetirse)
    │   ├── cbc:ID
    │   └── cac:ProcurementProject/cbc:Name
    │
    └── cac:AwardingCriteria                         (solo licitaciones, puede repetirse)
        ├── cbc:AwardingCriterionTypeCode            tipo de criterio
        ├── cbc:Description
        └── cbc:WeightNumeric                        peso del criterio sobre 100
```

### Valores codificados

**`ContractFolderStatusCode`** — estado del expediente:

| Código | Significado |
|--------|-------------|
| `PUB` | Publicado — en plazo de presentación de ofertas |
| `EV` | En evaluación — plazo cerrado, mesa reunida |
| `ADJ` | Adjudicado |
| `RES` | Resuelto — contrato formalizado |
| `ANUL` | Anulado |
| `DES` | Desistido — el órgano renuncia a contratar |

**`ContractingPartyTypeCode`** — tipo de administración del órgano:

| Código | Significado |
|--------|-------------|
| `1` | Administración General del Estado |
| `2` | Administración de las Comunidades Autónomas |
| `3` | Entidades que integran la Administración Local |
| `4` | Entidades gestoras y servicios comunes de la Seguridad Social |
| `5` | Organismos autónomos y entidades de derecho público |
| `6` | Consorcios |
| `7` | Fundaciones del sector público |
| `8` | Mutuas de accidentes de trabajo |
| `9` | Otros |

**`TypeCode`** — tipo de contrato en `ProcurementProject`:

| Código | Significado |
|--------|-------------|
| `1` | Obras |
| `2` | Concesión de obras |
| `3` | Gestión de servicios públicos |
| `4` | Suministros |
| `5` | Servicios |
| `6` | Concesión de servicios |
| `7` | Administrativo especial |
| `8` | Privado |
| `31` | Contrato mixto |

**`ProcedureCode`** — tipo de procedimiento:

| Código | Significado |
|--------|-------------|
| `OA` | Abierto |
| `OAA` | Abierto simplificado |
| `RE` | Restringido |
| `NE` | Negociado con publicidad |
| `NS` | Negociado sin publicidad |
| `DI` | Diálogo competitivo |
| `AS` | Asociación para la innovación |
| `MC` | Menor (contratos menores) |
| `LP` | Licitación con negociación |

**`UrgencyCode`** — urgencia del procedimiento:

| Código | Significado |
|--------|-------------|
| `ORD` | Ordinario |
| `URG` | Urgente |
| `EMG` | Emergencia |

**`FundingProgramCode`** — tipo de financiación:

| Código | Significado |
|--------|-------------|
| `1` | Sin fondos europeos — sujeto a regulación armonizada (SARA) |
| `2` | Sin fondos europeos — no sujeto a regulación armonizada |
| `3` | Con fondos europeos |

**`NoticeTypeCode`** — tipo de anuncio publicado:

| Código | Significado |
|--------|-------------|
| `1` | Anuncio de licitación |
| `2` | Anuncio de adjudicación |
| `3` | Anuncio de formalización |
| `4` | Anuncio de información previa |
| `5` | Otros |

**`AwardingCriterionTypeCode`** — tipo de criterio de adjudicación:

| Código | Significado |
|--------|-------------|
| `1` | Precio |
| `2` | Criterios cualitativos |
| `3` | Mejor relación calidad-precio |

**`PartyIdentification @schemeName`** — tipo de identificador del órgano o empresa:

| Valor | Significado |
|-------|-------------|
| `NIF` | Número de Identificación Fiscal (empresas españolas) |
| `DIR3` | Código de unidad orgánica del Directorio Común de Unidades y Oficinas (AGE) |
| `ID_PLATAFORMA` | Identificador interno asignado por PLACSP |
| `CIF` | Código de Identificación Fiscal (uso antiguo, equivalente a NIF) |

---

## Encargos a medios propios

También usan `ContractFolderStatus` como raíz, pero la estructura interna es diferente: no hay `ProcurementProject` ni `TenderResult`. Los importes y fechas son campos planos, y los actores son `OrderingParty` (quien encarga) y `ProprietaryMeans` (quien ejecuta).

```
atom:entry
└── cac-place-ext:ContractFolderStatus
    ├── cbc:ID                                       número de expediente (no ContractFolderID)
    ├── cbc-place-ext:EncargoProcedureStatusCode     estado propio de encargos
    ├── cbc:Name                                     objeto del encargo
    ├── cbc:Description
    ├── cbc:TypeCode                                 tipo de encargo
    ├── cbc:TotalAmount                              importe total (sin desglose IVA)
    ├── cbc:StartDate                                fechas directas en la raíz (sin PlannedPeriod)
    ├── cbc:EndDate
    │
    ├── cac:OrderingParty                            órgano que realiza el encargo
    │   └── cac:Party
    │       ├── cac:PartyIdentification/cbc:ID  @schemeName
    │       └── cac:PartyName/cbc:Name
    │
    └── cac:ProprietaryMeans                        medio propio que ejecuta el encargo
        └── cac:Party
            ├── cac:PartyIdentification/cbc:ID  @schemeName
            └── cac:PartyName/cbc:Name
```

Los encargos a medios propios no pasan por licitación pública; PLACSP los recoge por obligación de transparencia. Un medio propio es una entidad del sector público que actúa como instrumento de la Administración (p.ej. agencias, empresas públicas).

---

## Consultas preliminares de mercado

Usan `PreliminaryMarketConsultationStatus` como raíz. Son sondeos al mercado previos a la licitación, sin adjudicatario ni resultado económico. Comparten la estructura de `LocatedContractingParty` y `ValidNoticeInfo` con las licitaciones.

```
atom:entry
└── cac-place-ext:PreliminaryMarketConsultationStatus
    ├── cbc:ContractFolderID
    ├── cbc-place-ext:ContractFolderStatusCode
    ├── cbc:Name                                     objeto de la consulta
    ├── cbc:Description
    │
    ├── cac:RequiredCommodityClassification          puede repetirse
    │   └── cbc:ItemClassificationCode              código CPV orientativo
    │
    ├── cac:PlannedPeriod
    │   ├── cbc:StartDate
    │   └── cbc:EndDate
    │
    ├── cac-place-ext:LocatedContractingParty        estructura idéntica a licitaciones
    │   └── …
    │
    └── cac-place-ext:ValidNoticeInfo                estructura idéntica a licitaciones
        └── …
```

---

*La estructura de los feeds ATOM y los elementos CODICE fue analizada con ayuda de Claude 3.5 Sonnet (Anthropic).*
