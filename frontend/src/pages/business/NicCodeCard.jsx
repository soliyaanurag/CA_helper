import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import { MY_BUSINESS_KEY, saveNicCode, suggestNicCodes, useNicSearch } from "@/api/onboarding";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * "Business activity (NIC code)" on the Business profile page (ON10).
 *
 * 1. "Suggest codes" asks the backend for up to 3 real codes that fit the description
 *    (Gemini's picks, or keyword matches when AI is not available).
 * 2. Or the user searches the official list.
 * 3. The user ticks one and presses Confirm; only then is it saved.
 */
export function NicCodeCard({ nicCode }) {
  const queryClient = useQueryClient();
  const [suggestion, setSuggestion] = useState(null); // {picks, shortlist, ai_used}
  const [search, setSearch] = useState("");
  const [chosen, setChosen] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const results = useNicSearch(search);

  async function onSuggest() {
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      const answer = await suggestNicCodes();
      setSuggestion(answer);
      if (answer.picks.length > 0) {
        setChosen(answer.picks[0].code);
      }
    } catch (problem) {
      setError(errorMessage(problem));
    }
    setBusy(false);
  }

  async function onConfirm() {
    setError(null);
    setBusy(true);
    try {
      const code = await saveNicCode(chosen);
      // Show the new code on the page without loading the whole business again.
      const cached = queryClient.getQueryData(MY_BUSINESS_KEY);
      if (cached) {
        queryClient.setQueryData(MY_BUSINESS_KEY, { ...cached, nic_code: code });
      }
      setSuggestion(null);
      setSearch("");
      setChosen("");
      setSaved(true);
    } catch (problem) {
      setError(errorMessage(problem));
    }
    setBusy(false);
  }

  let searchRows = [];
  if (results.data) {
    searchRows = results.data;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Business activity (NIC code)</CardTitle>
        <CardDescription>
          The official code for what your business does. Forms like Udyam and GST registration ask
          for it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm">
          {nicCode ? (
            <>
              Your code: <span className="font-semibold">{nicCode.code}</span> ·{" "}
              {nicCode.description}
            </>
          ) : (
            "Not chosen yet."
          )}
        </p>
        {saved && (
          <p role="status" className="text-sm text-green-700">
            Saved.
          </p>
        )}

        <Button type="button" variant="outline" size="sm" onClick={onSuggest} disabled={busy}>
          {busy && !suggestion ? "Finding codes..." : "Suggest codes"}
        </Button>

        {suggestion && suggestion.picks.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No code matches your description. Search the list below.
          </p>
        )}
        {suggestion && suggestion.picks.length > 0 && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Suggested codes</legend>
            {!suggestion.ai_used && (
              <p className="text-xs text-muted-foreground">
                AI suggestions are not available right now; these are keyword matches.
              </p>
            )}
            {suggestion.picks.map((pick) => (
              <CodeOption
                key={pick.code}
                idPrefix="pick-"
                nic={pick}
                chosen={chosen}
                onChoose={setChosen}
                note={pick.reason}
                badge={pick.source === "ai" ? "AI suggestion, please check" : "Keyword match"}
              />
            ))}
          </fieldset>
        )}

        <div className="space-y-2">
          <Label htmlFor="nic-search">None of these? Search the list</Label>
          <Input
            id="nic-search"
            placeholder="e.g. bakery, tailoring or 10712"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          {searchRows.length > 0 && (
            <fieldset className="space-y-2">
              <legend className="sr-only">Search results</legend>
              {searchRows.map((nic) => (
                <CodeOption
                  key={nic.code}
                  idPrefix="found-"
                  nic={nic}
                  chosen={chosen}
                  onChoose={setChosen}
                />
              ))}
            </fieldset>
          )}
          {search.trim().length >= 2 && results.data && searchRows.length === 0 && (
            <p className="text-sm text-muted-foreground">No code found.</p>
          )}
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="button" onClick={onConfirm} disabled={busy || chosen === ""}>
          Confirm
        </Button>
      </CardContent>
    </Card>
  );
}

// One code as a radio button, with an optional reason and label.
// `idPrefix` keeps ids unique when a code is both suggested and found by the search.
function CodeOption({ idPrefix, nic, chosen, onChoose, note, badge }) {
  const id = idPrefix + nic.code;
  return (
    <label htmlFor={id} className="flex items-start gap-2 rounded-lg border p-2 text-sm">
      <input
        id={id}
        type="radio"
        name="nic-code"
        value={nic.code}
        checked={chosen === nic.code}
        onChange={() => onChoose(nic.code)}
        className="mt-1"
      />
      <span className="space-y-1">
        <span className="block">
          <span className="font-semibold">{nic.code}</span> · {nic.description}
        </span>
        {note && <span className="block text-xs text-muted-foreground">{note}</span>}
        {badge && <Badge variant="secondary">{badge}</Badge>}
      </span>
    </label>
  );
}
