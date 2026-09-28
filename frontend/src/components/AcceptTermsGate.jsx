import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import { FormCard } from "@/components/FormCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";

/**
 * Shown once, instead of the app, to a user who signed up before we asked for consent
 * (RequireRole renders it while `termsAccepted` is false).
 */
export function AcceptTermsGate() {
  const { acceptTerms, logout } = useAuth();
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function onAgree() {
    setError(null);
    setSaving(true);
    try {
      await acceptTerms();
    } catch (acceptError) {
      setError(errorMessage(acceptError));
      setSaving(false);
    }
  }

  return (
    <div className="p-8">
      <FormCard
        title="Our Terms and Privacy Policy"
        description="Before you continue, please read and accept how CA Helper stores and protects your data."
      >
        <Link
          to="/terms"
          target="_blank"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Read the Terms and Privacy Policy
        </Link>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex gap-2">
          <Button onClick={onAgree} disabled={saving}>
            {saving ? "Saving..." : "I agree"}
          </Button>
          <Button variant="outline" onClick={logout}>
            Log out
          </Button>
        </div>
      </FormCard>
    </div>
  );
}
