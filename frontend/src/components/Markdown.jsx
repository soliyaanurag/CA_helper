import ReactMarkdown from "react-markdown";

// Styles for the HTML that Markdown produces (headings, lists, links), written as
// Tailwind "child" selectors so each piece looks like the rest of the app.
const STYLES = [
  "space-y-3 text-sm leading-relaxed",
  "[&_h1]:text-lg [&_h1]:font-semibold",
  "[&_h2]:mt-5 [&_h2]:font-semibold",
  "[&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5",
  "[&_ol]:list-decimal [&_ol]:space-y-1 [&_ol]:pl-5",
  "[&_a]:text-primary [&_a]:underline-offset-4 [&_a]:hover:underline",
].join(" ");

/** Shows a Markdown text (e.g. a form's explanation from content/forms/) as formatted text. */
export function Markdown({ children }) {
  return (
    <div className={STYLES}>
      <ReactMarkdown
        components={{
          // Links to official portals open in a new tab.
          a: ({ href, children: text }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {text}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
