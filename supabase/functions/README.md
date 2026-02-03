# Supabase Edge Functions - LicitaFacil

Edge Functions para validacao e normalizacao de dados no edge (perto do usuario).

## Funcoes Disponiveis

### validate-password

Valida complexidade de senha.

**GET** `/functions/v1/validate-password`
- Retorna requisitos de senha

**POST** `/functions/v1/validate-password`
```json
{ "password": "SenhaForte123" }
```
Response:
```json
{
  "valid": true,
  "errors": [],
  "requirements": ["Minimo 8 caracteres", ...]
}
```

### normalize-text

Normaliza texto para comparacao (remove acentos, corrige OCR, etc).

**POST** `/functions/v1/normalize-text`
```json
{
  "text": "Execucao de pavimentacao asfaltica",
  "type": "description"  // ou "unit", "keywords", "similarity"
}
```

Types:
- `description`: Normaliza descricao (default)
- `unit`: Normaliza unidade de medida
- `keywords`: Extrai palavras-chave
- `similarity`: Calcula similaridade (requer `compareWith`)

### validate-unit

Valida e normaliza unidades de medida.

**GET** `/functions/v1/validate-unit`
- Retorna lista de unidades validas

**POST** `/functions/v1/validate-unit`
```json
{ "unit": "M2" }
```
Response:
```json
{
  "original": "M2",
  "normalized": "M2",
  "valid": true,
  "knownUnit": true
}
```

## Deploy

```bash
# Login no Supabase
supabase login

# Link ao projeto
supabase link --project-ref <project-id>

# Deploy de todas as funcoes
supabase functions deploy

# Deploy de uma funcao especifica
supabase functions deploy validate-password
```

## Desenvolvimento Local

```bash
# Iniciar servidor local
supabase start

# Testar funcao
curl -X POST http://localhost:54321/functions/v1/validate-password \
  -H "Content-Type: application/json" \
  -d '{"password": "Test123"}'
```
