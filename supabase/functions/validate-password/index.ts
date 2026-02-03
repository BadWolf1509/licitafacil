// Supabase Edge Function: validate-password
// Valida complexidade de senha sem necessidade de backend

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

// Configuracoes de validacao (espelhando backend/config/security.py)
const CONFIG = {
  minLength: 8,
  requireUppercase: true,
  requireLowercase: true,
  requireDigit: true,
  requireSpecial: false,
}

interface ValidationResult {
  valid: boolean
  errors: string[]
  requirements: string[]
}

function validatePassword(password: string): ValidationResult {
  const errors: string[] = []

  if (password.length < CONFIG.minLength) {
    errors.push(`Senha deve ter no minimo ${CONFIG.minLength} caracteres`)
  }

  if (CONFIG.requireUppercase && !/[A-Z]/.test(password)) {
    errors.push("Senha deve conter pelo menos uma letra maiuscula")
  }

  if (CONFIG.requireLowercase && !/[a-z]/.test(password)) {
    errors.push("Senha deve conter pelo menos uma letra minuscula")
  }

  if (CONFIG.requireDigit && !/\d/.test(password)) {
    errors.push("Senha deve conter pelo menos um numero")
  }

  if (CONFIG.requireSpecial && !/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;'`~]/.test(password)) {
    errors.push("Senha deve conter pelo menos um caractere especial")
  }

  return {
    valid: errors.length === 0,
    errors,
    requirements: getRequirements(),
  }
}

function getRequirements(): string[] {
  const requirements: string[] = [`Minimo ${CONFIG.minLength} caracteres`]

  if (CONFIG.requireUppercase) {
    requirements.push("Pelo menos uma letra maiuscula")
  }

  if (CONFIG.requireLowercase) {
    requirements.push("Pelo menos uma letra minuscula")
  }

  if (CONFIG.requireDigit) {
    requirements.push("Pelo menos um numero")
  }

  if (CONFIG.requireSpecial) {
    requirements.push("Pelo menos um caractere especial (!@#$%^&*...)")
  }

  return requirements
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
    // GET: Retorna requisitos
    if (req.method === "GET") {
      return new Response(
        JSON.stringify({ requisitos: getRequirements() }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 200,
        }
      )
    }

    // POST: Valida senha
    if (req.method === "POST") {
      const { password } = await req.json()

      if (!password || typeof password !== "string") {
        return new Response(
          JSON.stringify({ error: "Campo 'password' e obrigatorio" }),
          {
            headers: { ...corsHeaders, "Content-Type": "application/json" },
            status: 400,
          }
        )
      }

      const result = validatePassword(password)

      return new Response(
        JSON.stringify(result),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 200,
        }
      )
    }

    return new Response(
      JSON.stringify({ error: "Metodo nao permitido" }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 405,
      }
    )
  } catch (error) {
    return new Response(
      JSON.stringify({ error: "Erro interno" }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 500,
      }
    )
  }
})
