// Supabase Edge Function: normalize-text
// Normaliza texto para comparacao (remove acentos, OCR artifacts, etc)

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

// Stopwords para extracao de palavras-chave
const STOPWORDS = new Set([
  'DE', 'DO', 'DA', 'EM', 'PARA', 'COM', 'E', 'A', 'O', 'AS', 'OS',
  'UN', 'M2', 'M3', 'ML', 'M', 'VB', 'KG', 'INCLUSIVE', 'INCLUSIV',
  'TIPO', 'MODELO', 'TRACO'
])

/**
 * Remove acentos de texto usando normalizacao Unicode
 */
function removeAccents(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

/**
 * Normaliza descricao para comparacao
 * Remove acentos, espacos extras, pontuacao e converte para maiusculas
 * Corrige erros comuns de OCR
 */
function normalizeDescription(desc: string): string {
  if (!desc) return ""

  // Remover acentos
  let text = removeAccents(desc)

  // Converter para maiusculas
  text = text.toUpperCase()

  // Normalizar pontuacao (OCR pode confundir ; com , ou .)
  text = text.replace(/;/g, ',').replace(/:/g, ',')

  // Remover toda pontuacao para comparacao mais robusta
  text = text.replace(/[^\w\s]/g, ' ')

  // Corrigir erros comuns de OCR em numeros/letras
  // I no meio de numeros geralmente e 1
  text = text.replace(/(\d)I(\d)/g, '$11')
  text = text.replace(/(\d)l(\d)/g, '$11')  // l minusculo
  text = text.replace(/(\d)O(\d)/g, '$10')  // O -> 0

  // Remover espacos extras
  return text.split(/\s+/).filter(Boolean).join(' ')
}

/**
 * Normaliza unidade para comparacao
 * Converte expoentes, corrige artefatos de OCR e padroniza caixa
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
 * Extrai palavras-chave significativas da descricao
 */
function extractKeywords(desc: string): string[] {
  const normalized = normalizeDescription(desc)
  const words = normalized.split(/\s+/).filter(Boolean)
  return words.filter(w => !STOPWORDS.has(w) && w.length > 1)
}

/**
 * Calcula similaridade entre duas descricoes (0.0 a 1.0)
 */
function descriptionSimilarity(left: string, right: string): number {
  const leftKw = new Set(extractKeywords(left))
  const rightKw = new Set(extractKeywords(right))

  if (leftKw.size === 0 || rightKw.size === 0) return 0.0

  const intersection = [...leftKw].filter(w => rightKw.has(w)).length
  return intersection / Math.max(leftKw.size, rightKw.size)
}

interface NormalizeRequest {
  text: string
  type?: 'description' | 'unit' | 'keywords' | 'similarity'
  compareWith?: string
}

interface NormalizeResponse {
  original: string
  normalized: string
  keywords?: string[]
  similarity?: number
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
    if (req.method !== "POST") {
      return new Response(
        JSON.stringify({ error: "Apenas POST permitido" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 405 }
      )
    }

    const body: NormalizeRequest = await req.json()
    const { text, type = 'description', compareWith } = body

    if (!text || typeof text !== "string") {
      return new Response(
        JSON.stringify({ error: "Campo 'text' e obrigatorio" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      )
    }

    let response: NormalizeResponse = {
      original: text,
      normalized: ''
    }

    switch (type) {
      case 'unit':
        response.normalized = normalizeUnit(text)
        break

      case 'keywords':
        response.normalized = normalizeDescription(text)
        response.keywords = extractKeywords(text)
        break

      case 'similarity':
        if (!compareWith) {
          return new Response(
            JSON.stringify({ error: "Campo 'compareWith' e obrigatorio para type=similarity" }),
            { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
          )
        }
        response.normalized = normalizeDescription(text)
        response.similarity = descriptionSimilarity(text, compareWith)
        break

      case 'description':
      default:
        response.normalized = normalizeDescription(text)
        break
    }

    return new Response(
      JSON.stringify(response),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
    )

  } catch (error) {
    return new Response(
      JSON.stringify({ error: "Erro interno" }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    )
  }
})
