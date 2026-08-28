import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase: SupabaseClient | null =
  url && anonKey
    ? createClient(url, anonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
          // The app is deployed as a static client. Implicit flow keeps the
          // confirmation session in the redirect URL instead of requiring a
          // PKCE verifier in the same browser storage context.
          flowType: "implicit",
        },
      })
    : null;
