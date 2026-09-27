import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Plain-language terms: what we store, how it is protected, who sees it, what we do not do.
const SECTIONS = [
  {
    title: "What CA Helper does",
    points: [
      "It tells your business which tax filings apply and when they are due, helps you file them yourself, or connects you with a Chartered Accountant (CA).",
      "It never files a return for you and has no access to the government portals. Filing is done by you or by your CA.",
      "The profile and due dates are a guide. Check anything important with a CA.",
    ],
  },
  {
    title: "What we store",
    points: [
      "Your account: name, email and a hashed password (we never store the password itself).",
      "Your business details: name, type, state, address, turnover, PAN, GSTIN, TAN, phone and the answers you give on the profile form.",
      "Your filings and their status, and the documents you or your CA upload.",
    ],
  },
  {
    title: "How we protect it",
    points: [
      "PAN, GSTIN, TAN and phone numbers are encrypted in our database.",
      "Uploaded documents are encrypted and stored on our server; they are never sent anywhere else.",
      "Our AI assistant never receives your PAN, GSTIN, TAN, name, email, phone, address or documents.",
    ],
  },
  {
    title: "Who sees your data",
    points: [
      "A CA you send a request to sees only a summary (business type, state, size) and the filings in the request, not your PAN, GSTIN, TAN or documents.",
      "Once you and a CA agree, that CA sees your full profile, but only the filings in that engagement and the documents linked to them. When the work ends, their access ends.",
      "Our admins see account and verification details, never the contents of your documents.",
    ],
  },
];

/** /terms: the Terms and Privacy Policy, in plain language. */
export function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Terms and Privacy Policy</h1>
      {SECTIONS.map((section) => (
        <Card key={section.title}>
          <CardHeader>
            <CardTitle>{section.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-2 pl-5 text-sm">
              {section.points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
