// Type declarations for Deno standard library used in Edge Functions

declare module 'https://deno.land/std@0.168.0/http/server.ts' {
  export function serve(
    handler: (request: Request) => Response | Promise<Response>
  ): void;
}
