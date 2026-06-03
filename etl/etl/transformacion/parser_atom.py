import os
from typing import List, Dict, Optional, Any
from lxml import etree
from dateutil import parser as dateutil_parser
import glob
import re


class ParserATOM:
    # namespaces necesarios para parsear el xml de PLACSP
    # sin esto no funciona el find/findall
    NAMESPACES = {
        'atom': 'http://www.w3.org/2005/Atom',
        'cac': 'urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2',
        'cac-place-ext': 'urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2',
        'cbc-place-ext': 'urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2'
    }

    def __init__(self, tipo: str = 'licitaciones'):
        self.tipo = tipo

    def _parse_bool(self, valor_str: Optional[str]) -> Optional[bool]:
        if not valor_str:
            return None
        v = valor_str.lower().strip()
        if v in ('true', '1', 'yes', 'si', 'sí'):
            return True
        if v in ('false', '0', 'no'):
            return False
        return None

    def _parse_fecha(self, fecha_str: Optional[str]) -> Optional[str]:
        if not fecha_str:
            return None
        try:
            return dateutil_parser.parse(fecha_str).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return fecha_str

    # helpers para navegar el xml sin repetir try/except en cada extractor

    def _get_text(self, element: etree.Element, xpath: str) -> Optional[str]:
        try:
            result = element.find(xpath, self.NAMESPACES)
            if result is not None and result.text:
                return result.text.strip() or None
            return None
        except Exception:
            return None

    def _get_attribute(self, element: etree.Element, xpath: str, attr: str) -> Optional[str]:
        try:
            result = element.find(xpath, self.NAMESPACES)
            return result.get(attr) if result is not None else None
        except Exception:
            return None

    def _extraer_expediente(self, codice: etree.Element) -> Dict:
        return {
            'num_expediente': self._get_text(codice, 'cbc:ContractFolderID'),
            'estado': self._get_text(codice, 'cbc-place-ext:ContractFolderStatusCode')
        }

    def _extraer_condiciones_licitacion(self, codice: etree.Element) -> Dict:
        datos = {}
        terms = codice.find('cac:TenderingTerms', self.NAMESPACES)
        if terms is None:
            return datos
        funding = terms.find('cbc:FundingProgramCode', self.NAMESPACES)
        if funding is not None:
            datos['financiacion_codigo'] = funding.text
            datos['financiacion_descripcion'] = funding.get('name')
        datos['requiere_garantia'] = self._get_text(terms, 'cbc:RequiredFinancialGuarantee')
        return datos

    def _extraer_info_publicacion(self, codice: etree.Element) -> Dict:
        datos = {}
        notice = codice.find('cac-place-ext:ValidNoticeInfo', self.NAMESPACES)
        if notice is None:
            return datos
        datos['tipo_anuncio'] = self._get_text(notice, 'cbc-place-ext:NoticeTypeCode')
        pub_status = notice.find('cac-place-ext:AdditionalPublicationStatus', self.NAMESPACES)
        if pub_status is not None:
            datos['medio_publicacion'] = self._get_text(pub_status, 'cbc-place-ext:PublicationMediaName')
            datos['fecha_publicacion'] = self._get_text(
                pub_status,
                'cac-place-ext:AdditionalPublicationDocumentReference/cbc:IssueDate'
            )
        return datos

    def _extraer_metadatos_atom(self, entry: etree.Element) -> Dict:
        # el link no siempre tiene rel="alternate", buscamos el primero que haya
        link_elem = entry.find('atom:link', self.NAMESPACES)
        url = link_elem.get('href') if link_elem is not None else None
        return {
            'id_atom': self._get_text(entry, 'atom:id'),
            'titulo': self._get_text(entry, 'atom:title'),
            'summary': self._get_text(entry, 'atom:summary'),
            'url_placsp': url,
            'fecha_actualizacion': self._parse_fecha(self._get_text(entry, 'atom:updated'))
        }

    def _extraer_proceso_licitacion(self, codice: etree.Element) -> Dict:
        datos = {}
        process = codice.find('cac:TenderingProcess', self.NAMESPACES)
        if process is None:
            return datos
        datos['tipo_procedimiento'] = self._get_text(process, 'cbc:ProcedureCode')
        datos['urgencia'] = self._get_text(process, 'cbc:UrgencyCode')
        deadline = process.find('cac:TenderSubmissionDeadlinePeriod', self.NAMESPACES)
        if deadline is not None:
            datos['plazo_presentacion_fecha'] = self._get_text(deadline, 'cbc:EndDate')
            datos['plazo_presentacion_hora'] = self._get_text(deadline, 'cbc:EndTime')
        opening = process.find('cac:OpenTenderEvent', self.NAMESPACES)
        if opening is not None:
            datos['apertura_fecha'] = self._get_text(opening, 'cbc:OccurrenceDate')
            datos['apertura_hora'] = self._get_text(opening, 'cbc:OccurrenceTime')
            datos['apertura_descripcion'] = self._get_text(opening, 'cbc:Description')
        return datos

    def _extraer_especificos_licitacion(self, codice: etree.Element) -> Dict:
        # lotes y criterios, solo para licitaciones (no contratos menores)
        datos = {}
        lots = codice.findall('cac:ProcurementProjectLot', self.NAMESPACES)
        if lots:
            datos['num_lotes'] = len(lots)
            datos['lotes'] = [
                {'id': self._get_text(l, 'cbc:ID'), 'descripcion': self._get_text(l, 'cac:ProcurementProject/cbc:Name')}
                for l in lots
            ]
        criteria = codice.findall('cac:AwardingCriteria', self.NAMESPACES)
        if criteria:
            datos['criterios_adjudicacion'] = [
                {
                    'tipo': self._get_text(c, 'cbc:AwardingCriterionTypeCode'),
                    'descripcion': self._get_text(c, 'cbc:Description'),
                    'peso': self._get_text(c, 'cbc:Weight')
                }
                for c in criteria
            ]
        return datos

    def _extraer_proyecto_contratacion(self, codice: etree.Element) -> Dict:
        datos = {}
        project = codice.find('cac:ProcurementProject', self.NAMESPACES)
        if project is None:
            return datos

        datos['objeto'] = self._get_text(project, 'cbc:Name')
        datos['descripcion'] = self._get_text(project, 'cbc:Description')
        datos['tipo_contrato'] = self._get_text(project, 'cbc:TypeCode')  # 1=obras, 2=servicios, 3=suministros...
        datos['subtipo_contrato'] = self._get_text(project, 'cbc:SubTypeCode')

        budget = project.find('cac:BudgetAmount', self.NAMESPACES)
        if budget is not None:
            v = self._get_text(budget, 'cbc:TaxExclusiveAmount')
            datos['presupuesto_sin_iva'] = float(v) if v else None
            v = self._get_text(budget, 'cbc:TotalAmount')
            datos['presupuesto_con_iva'] = float(v) if v else None
            tax_elem = budget.find('cbc:TaxExclusiveAmount', self.NAMESPACES)
            if tax_elem is not None:
                datos['moneda'] = tax_elem.get('currencyID')

        v = self._get_text(project, 'cbc:EstimatedOverallContractAmount')
        datos['valor_estimado'] = float(v) if v else None

        location = project.find('cac:RealizedLocation', self.NAMESPACES)
        if location is not None:
            datos['lugar_ejecucion'] = self._get_text(location, 'cbc:CountrySubentity')
            datos['lugar_ejecucion_codigo'] = self._get_text(location, 'cbc:CountrySubentityCode')
            address = location.find('cac:Address', self.NAMESPACES)
            if address is not None:
                datos['lugar_ejecucion_pais'] = self._get_text(address, 'cac:Country/cbc:IdentificationCode')

        period = project.find('cac:PlannedPeriod', self.NAMESPACES)
        if period is not None:
            duracion = self._get_text(period, 'cbc:DurationMeasure')
            if duracion:
                datos['duracion_valor'] = float(duracion)
                datos['duracion_unidad'] = self._get_attribute(period, 'cbc:DurationMeasure', 'unitCode')
            datos['fecha_inicio'] = self._get_text(period, 'cbc:StartDate')
            datos['fecha_fin'] = self._get_text(period, 'cbc:EndDate')

        cpv_codes = project.findall('cac:RequiredCommodityClassification/cbc:ItemClassificationCode', self.NAMESPACES)
        if cpv_codes:
            datos['codigos_cpv'] = [cpv.text for cpv in cpv_codes if cpv.text]

        return datos

    def _extraer_resultado_adjudicacion(self, codice: etree.Element) -> Dict:
        datos = {}
        result = codice.find('cac:TenderResult', self.NAMESPACES)
        if result is None:
            return datos

        datos['resultado_codigo'] = self._get_text(result, 'cbc:ResultCode')
        datos['fecha_adjudicacion'] = self._get_text(result, 'cbc:AwardDate')
        datos['fecha_formalizacion'] = self._get_text(result, 'cbc:ReceivedDate')
        v = self._get_text(result, 'cbc:ReceivedTenderQuantity')
        datos['num_ofertas_recibidas'] = int(float(v)) if v else None
        datos['adjudicado_pyme'] = self._parse_bool(self._get_text(result, 'cbc:SMEAwardedIndicator'))

        winner = result.find('cac:WinningParty', self.NAMESPACES)
        if winner is not None:
            ids = winner.findall('cac:PartyIdentification/cbc:ID', self.NAMESPACES)
            id_fallback = None
            id_fallback_tipo = None
            for id_elem in ids:
                scheme = id_elem.get('schemeName', '')
                valor = id_elem.text
                if not valor:
                    continue
                if scheme in ('NIF', 'CIF'):
                    datos['adjudicatario_nif'] = valor
                    break
                elif id_fallback is None:
                    # guardamos el primero que no sea NIF por si acaso (empresas extranjeras)
                    id_fallback = valor
                    id_fallback_tipo = scheme or None

            if datos.get('adjudicatario_nif'):
                datos['adjudicatario_id'] = datos['adjudicatario_nif']
                datos['adjudicatario_id_tipo'] = 'NIF'
            elif id_fallback:
                datos['adjudicatario_id'] = id_fallback
                datos['adjudicatario_id_tipo'] = id_fallback_tipo

            datos['adjudicatario_nombre'] = self._get_text(winner, 'cac:PartyName/cbc:Name')
            location = winner.find('cac:PhysicalLocation', self.NAMESPACES)
            if location is not None:
                datos['adjudicatario_pais'] = self._get_text(location, 'cac:Address/cac:Country/cbc:IdentificationCode')

        awarded = result.find('cac:AwardedTenderedProject/cac:LegalMonetaryTotal', self.NAMESPACES)
        if awarded is not None:
            v = self._get_text(awarded, 'cbc:TaxExclusiveAmount')
            datos['importe_adjudicacion_sin_iva'] = float(v) if v else None
            v = self._get_text(awarded, 'cbc:PayableAmount')
            datos['importe_adjudicacion_con_iva'] = float(v) if v else None

        return datos

    def _extraer_organo_contratacion(self, codice: etree.Element) -> Dict:
        datos = {}
        organo = codice.find('.//cac-place-ext:LocatedContractingParty', self.NAMESPACES)
        if organo is None:
            return datos

        datos['organo_tipo'] = self._get_text(organo, 'cbc:ContractingPartyTypeCode')
        actividades = organo.findall('cbc:ActivityCode', self.NAMESPACES)
        datos['organo_actividades'] = [act.text for act in actividades if act.text]
        datos['organo_perfil_url'] = self._get_text(organo, 'cbc:BuyerProfileURIID')

        party = organo.find('cac:Party', self.NAMESPACES)
        if party is not None:
            # pueden venir varios identificadores: NIF, DIR3, ID_PLATAFORMA
            for id_elem in party.findall('cac:PartyIdentification/cbc:ID', self.NAMESPACES):
                scheme = id_elem.get('schemeName')
                if scheme == 'NIF':
                    datos['organo_nif'] = id_elem.text
                elif scheme == 'DIR3':
                    datos['organo_dir3'] = id_elem.text
                elif scheme == 'ID_PLATAFORMA':
                    datos['organo_id_plataforma'] = id_elem.text

            datos['organo_nombre'] = self._get_text(party, 'cac:PartyName/cbc:Name')

            address = party.find('cac:PostalAddress', self.NAMESPACES)
            if address is not None:
                datos['organo_ciudad'] = self._get_text(address, 'cbc:CityName')
                datos['organo_codigo_postal'] = self._get_text(address, 'cbc:PostalZone')
                datos['organo_direccion'] = self._get_text(address, 'cac:AddressLine/cbc:Line')
                datos['organo_pais'] = self._get_text(address, 'cac:Country/cbc:IdentificationCode')

            contact = party.find('cac:Contact', self.NAMESPACES)
            if contact is not None:
                datos['organo_contacto_nombre'] = self._get_text(contact, 'cbc:Name')
                datos['organo_telefono'] = self._get_text(contact, 'cbc:Telephone')
                datos['organo_fax'] = self._get_text(contact, 'cbc:Telefax')
                datos['organo_email'] = self._get_text(contact, 'cbc:ElectronicMail')

        # jerarquia organizativa: ministerio > secretaria > direccion general...
        jerarquia = []
        parent = organo.find('cac-place-ext:ParentLocatedParty', self.NAMESPACES)
        while parent is not None:
            nombre = self._get_text(parent, 'cac:PartyName/cbc:Name')
            if nombre:
                jerarquia.append(nombre)
            parent = parent.find('cac-place-ext:ParentLocatedParty', self.NAMESPACES)
        if jerarquia:
            datos['organo_jerarquia'] = jerarquia

        return datos

    def _extraer_encargo(self, codice: etree.Element) -> Dict:
        datos = {}
        datos['num_expediente'] = self._get_text(codice, 'cbc:ID')
        datos['estado'] = self._get_text(codice, 'cbc-place-ext:EncargoProcedureStatusCode')
        datos['objeto'] = self._get_text(codice, 'cbc:Name')
        datos['descripcion'] = self._get_text(codice, 'cbc:Description')
        datos['tipo_encargo'] = self._get_text(codice, 'cbc:TypeCode')
        v = self._get_text(codice, 'cbc:TotalAmount')
        datos['importe'] = float(v) if v else None

        ordering = codice.find('cac:OrderingParty', self.NAMESPACES)
        if ordering is not None:
            party = ordering.find('cac:Party', self.NAMESPACES)
            if party is not None:
                datos['organo_encomendante_nombre'] = self._get_text(party, 'cac:PartyName/cbc:Name')
                for id_elem in party.findall('cac:PartyIdentification/cbc:ID', self.NAMESPACES):
                    if id_elem.get('schemeName') == 'NIF':
                        datos['organo_encomendante_nif'] = id_elem.text
                        break

        proprietary = codice.find('cac:ProprietaryMeans', self.NAMESPACES)
        if proprietary is not None:
            party = proprietary.find('cac:Party', self.NAMESPACES)
            if party is not None:
                datos['medio_propio_nombre'] = self._get_text(party, 'cac:PartyName/cbc:Name')
                for id_elem in party.findall('cac:PartyIdentification/cbc:ID', self.NAMESPACES):
                    if id_elem.get('schemeName') == 'NIF':
                        datos['medio_propio_nif'] = id_elem.text
                        break

        datos['fecha_inicio'] = self._get_text(codice, 'cbc:StartDate')
        datos['fecha_fin'] = self._get_text(codice, 'cbc:EndDate')
        return datos

    def _extraer_consulta(self, codice: etree.Element) -> Dict:
        # consultas preliminares: no son contratos, reutilizamos metodos de licitaciones
        datos = {}
        datos['num_expediente'] = self._get_text(codice, 'cbc:ContractFolderID')
        datos['estado'] = self._get_text(codice, 'cbc-place-ext:ContractFolderStatusCode')
        datos['objeto'] = self._get_text(codice, 'cbc:Name')
        datos['descripcion'] = self._get_text(codice, 'cbc:Description')
        datos.update(self._extraer_organo_contratacion(codice))
        cpv_codes = codice.findall('.//cac:RequiredCommodityClassification/cbc:ItemClassificationCode', self.NAMESPACES)
        if cpv_codes:
            datos['codigos_cpv'] = [c.text for c in cpv_codes if c.text]
        period = codice.find('.//cac:PlannedPeriod', self.NAMESPACES)
        if period is not None:
            datos['fecha_inicio'] = self._get_text(period, 'cbc:StartDate')
            datos['fecha_fin'] = self._get_text(period, 'cbc:EndDate')
        datos.update(self._extraer_info_publicacion(codice))
        return datos

    def _extraer_licitacion_contrato(self, codice: etree.Element, tipo: str) -> Dict:
        datos = {}
        datos.update(self._extraer_expediente(codice))
        datos.update(self._extraer_organo_contratacion(codice))
        datos.update(self._extraer_proyecto_contratacion(codice))
        datos.update(self._extraer_resultado_adjudicacion(codice))
        datos.update(self._extraer_proceso_licitacion(codice))
        datos.update(self._extraer_condiciones_licitacion(codice))
        datos.update(self._extraer_info_publicacion(codice))
        if tipo == 'licitaciones':
            datos.update(self._extraer_especificos_licitacion(codice))
        return datos

    def _extraer_entry_completo(self, entry: etree.Element, tipo: str) -> Optional[Dict]:
        try:
            datos = self._extraer_metadatos_atom(entry)
            if tipo == 'consultas':
                codice = entry.find('cac-place-ext:PreliminaryMarketConsultationStatus', self.NAMESPACES)
            else:
                codice = entry.find('cac-place-ext:ContractFolderStatus', self.NAMESPACES)
            if codice is None:
                return None
            if tipo in ['licitaciones', 'menores']:
                datos.update(self._extraer_licitacion_contrato(codice, tipo))
            elif tipo == 'encargos':
                datos.update(self._extraer_encargo(codice))
            elif tipo == 'consultas':
                datos.update(self._extraer_consulta(codice))
            return datos
        except Exception:
            return None

    def parsear_archivo(self, ruta_archivo: str, tipo: Optional[str] = None) -> List[Dict]:
        """lee un .atom y devuelve lista de registros"""
        if not os.path.exists(ruta_archivo):
            raise FileNotFoundError(f"Archivo no encontrado: {ruta_archivo}")

        tipo_efectivo = tipo or self.tipo

        ruta_normalizada = ruta_archivo.replace('\\', '/')
        if '/perfil/' in ruta_normalizada:
            fuente = 'perfil'
        elif '/agregacion/' in ruta_normalizada:
            fuente = 'agregacion'
        else:
            fuente = 'unknown'

        match_periodo = re.search(r'(\d{4}-\d{2})', ruta_normalizada)
        periodo = match_periodo.group(1) if match_periodo else None

        try:
            tree = etree.parse(ruta_archivo)
            root = tree.getroot()
            entries = root.findall('atom:entry', self.NAMESPACES)
            registros = []
            for entry in entries:
                try:
                    registro = self._extraer_entry_completo(entry, tipo_efectivo)
                    if registro:
                        registro['_fuente'] = fuente
                        if periodo:
                            registro['_periodo'] = periodo
                        registros.append(registro)
                except Exception:
                    continue
            return registros
        except etree.XMLSyntaxError as e:
            print(f"error parseando xml: {e}")
            return []
