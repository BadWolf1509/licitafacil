// Supabase Edge Function: validate-unit
// Valida e normaliza unidades de medida de construcao civil

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

// Unidades de medida validas para construcao civil/engenharia
const VALID_UNITS = new Set([
  // Metricas lineares
  'M', 'M2', 'M3', 'ML', 'KM',
  // Unidades
  'UN', 'UND', 'UNID', 'UNIDADE', 'PC', 'PECA',
  // Peso/Volume
  'KG', 'T', 'TON', 'L', 'LT', 'LITRO',
  // Conjuntos
  'CJ', 'CONJ', 'CONJUNTO', 'PAR', 'PARES', 'JG', 'JOGO',
  // Globais
  'VB', 'VERBA', 'GL', 'GLOBAL', 'SV', 'SERV',
  // Hora/Dia
  'H', 'HR', 'HORA', 'DIA', 'D', 'MES',
  // Outros comuns
  'SC', 'SACO', 'PT', 'PONTO', 'FX', 'FAIXA', 'CX', 'CAIXA',
])

/**
 * Remove acentos de texto usando normalizacao Unicode
 */
function removeAccents(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

/**
 * Normaliza unidade para comparacao
 */
function normalizeUnit(unit: string): string {
  if (!unit) return ""

  let normalized = unit.trim().toUpperCase()

  // Converter simbolos de area/volume
  normalized = normalized.replace(/M\s*[\?\u00b0\u00ba]/g, 'M2')
  normalized = normalized.replace(/M²/g, 'M2').replace(/M³/g, 'M3')

  // Converter subscripts e superscripts Unicode
  const subscriptMap: Record<string, string> = {
    '\u2080': '0', '\u2081': '1', '\u2082': '2', '\u2083': '3', '\u2084': '4',
    '\u2085': '5', '\u2086': '6', '\u2087': '7', '\u2088': '8', '\u2089': '9',
    '\u2070': '0', '\u00b9': '1', '\u00b2': '2', '\u00b3': '3', '\u2074': '4',
    '\u2075': '5', '\u2076': '6', '\u2077': '7', '\u2078': '8', '\u2079': '9',
  }
  for (const [sub, digit] of Object.entries(subscriptMap)) {
    normalized = normalized.split(sub).join(digit)
  }

  // Converter expoentes em formato texto
  normalized = normalized.replace(/M\^2/g, 'M2').replace(/M\^3/g, 'M3')

  // Remover acentos e caracteres nao ASCII
  normalized = removeAccents(normalized)
  normalized = normalized.replace(/[^A-Z0-9]/g, '')

  // Corrigir duplicacoes comuns de OCR
  while (normalized.includes('NN') && normalized !== 'UN') {
    normalized = normalized.replace(/NN/g, 'N')
  }
  while (normalized.includes('MM')) {
    normalized = normalized.replace(/MM/g, 'M')
  }
  while (normalized.includes('UU')) {
    normalized = normalized.replace(/UU/g, 'U')
  }

  // Mapear unidades conhecidas
  const unitCorrections: Record<string, string> = {
    'M23': 'M2', 'M32': 'M3', 'M22': 'M2', 'M33': 'M3',
    'EM2': 'M2', 'EM3': 'M3', 'UNI': 'UN', 'UND': 'UN',
    'UNID': 'UN', 'UNIDADE': 'UN', 'METRO': 'M', 'METROS': 'M',
    'KGS': 'KG', 'MOS': 'MES', 'LT': 'L', 'TON': 'T'
  }

  if (unitCorrections[normalized]) {
    normalized = unitCorrections[normalized]
  }

  return normalized
}

/**
 * Verifica se uma unidade de medida e valida
 */
function isValidUnit(unit: string): boolean {
  if (!unit) return false

  const normalized = normalizeUnit(unit)
  if (!normalized) return false

  // Verificar se esta na lista de unidades validas
  if (VALID_UNITS.has(normalized)) return true

  // Unidades curtas (<=3 chars) sao geralmente validas
  if (normalized.length <= 3) return true

  // Unidades muito longas (>5 chars) sao provavelmente palavras do texto
  if (normalized.length > 5) return false

  return false
}

interface ValidateRequest {
  unit: string
}

interface ValidateResponse {
  original: string
  normalized: string
  valid: boolean
  knownUnit: boolean
}

serve(async (req) => {
  // CORS headers
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  }

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders })
  }

  try {
    // GET: Retorna lista de unidades validas
    if (req.method === "GET") {
      return new Response(
        JSON.stringify({ units: Array.from(VALID_UNITS).sort() }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      )
    }

    // POST: Valida unidade
    if (req.method === "POST") {
      const body: ValidateRequest = await req.json()
      const { unit } = body

      if (!unit || typeof unit !== "string") {
        return new Response(
          JSON.stringify({ error: "Campo 'unit' e obrigatorio" }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
        )
      }

      const normalized = normalizeUnit(unit)
      const response: ValidateResponse = {
        original: unit,
        normalized,
        valid: isValidUnit(unit),
        knownUnit: VALID_UNITS.has(normalized)
      }

      return new Response(
        JSON.stringify(response),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      )
    }

    return new Response(
      JSON.stringify({ error: "Metodo nao permitido" }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 405 }
    )

  } catch (error) {
    return new Response(
      JSON.stringify({ error: "Erro interno" }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    )
  }
})
