import Head from "next/head";
import Link from "next/link";

import AppShell from "../components/AppShell";
import CapabilityCard from "../components/CapabilityCard";
import PageHero from "../components/PageHero";

const capabilities = [
  {
    href: "/rag",
    title: "Legal Assistant",
    label: "RAG",
    description:
      "Ask a question about Jordanian labour law and receive an initial explanation supported by retrieved legal references.",
    features: [
      "Source-grounded answers",
      "Clear legal references",
      "Retrieved evidence",
      "Safe abstention when evidence is insufficient",
    ],
    action: "Open Legal Assistant",
    icon: "rag",
  },
  {
    href: "/kg",
    title: "Legal Knowledge Graph",
    label: "Knowledge Graph",
    description: "Explore connections between laws, articles, and legal topics through Neo4j and Text2Cypher.",
    features: [
      "Explore related articles",
      "Inspect legal relationships",
      "Review structured results",
      "Access technical details when needed",
    ],
    action: "Explore Knowledge Graph",
    icon: "kg",
  },
];

const steps = [
  {
    title: "Enter your legal question",
    description: "Start with an Arabic labour-law question or relationship query.",
  },
  {
    title: "Retrieve evidence or graph relationships",
    description: "Use semantic retrieval for grounded answers or Neo4j relationships for graph exploration.",
  },
  {
    title: "Review the result and references",
    description: "Inspect the answer, references, evidence, graph records, and legal notice before relying on it.",
  },
];

const trustPrinciples = [
  "Source-grounded answers",
  "Visible legal references",
  "Inspectable results",
  "Responsible legal disclaimer",
];

export default function Home() {
  return (
    <AppShell>
      <Head>
        <title>Lawz AI JO | Jordanian Labour Law Assistant</title>
        <meta
          name="description"
          content="An experimental legal-tech platform for exploring Jordanian labour law with RAG and a legal knowledge graph."
        />
      </Head>

      <div className="page-container">
        <PageHero
          className="page-hero--landing"
          eyebrow="Source-grounded legal intelligence"
          title="Understand Jordanian Labour Law with clarity"
          description="An experimental legal-tech platform combining source-grounded semantic retrieval with a knowledge graph for exploring Jordanian labour-law articles and relationships."
        >
          <div className="landing-hero-aside">
            <div className="hero-system-panel" aria-label="Lawz AI JO capability overview">
              <div className="hero-system-panel__header">
                <span className="hero-system-panel__title">Two complementary capabilities</span>
                <span className="status-badge status-badge--accent">Informational use only</span>
              </div>
              <div className="hero-system-panel__body">
                <div className="signal-row">
                  <strong>RAG</strong>
                  <span>Retrieves legal passages, prepares a grounded answer, and keeps references visible.</span>
                </div>
                <div className="signal-row">
                  <strong>Graph</strong>
                  <span>Explores Articles, Laws, Topics, and Relationships through Neo4j and Text2Cypher.</span>
                </div>
              </div>
            </div>
            <div className="landing-hero-actions">
              <Link href="/rag" className="button button--primary">
                Open Legal Assistant
              </Link>
              <Link href="/kg" className="button button--secondary">
                Explore Knowledge Graph
              </Link>
            </div>
          </div>
        </PageHero>

        <section className="section" aria-labelledby="capabilities-title">
          <div className="section__header">
            <div>
              <h2 id="capabilities-title">Choose a capability</h2>
              <p>Both tools are part of the same Lawz AI JO platform and are designed for different legal research workflows.</p>
            </div>
          </div>
          <div className="capability-grid">
            {capabilities.map((capability) => (
              <CapabilityCard key={capability.href} {...capability} />
            ))}
          </div>
        </section>

        <section className="section" aria-labelledby="workflow-title">
          <div className="section__header">
            <div>
              <h2 id="workflow-title">How the platform works</h2>
            </div>
          </div>
          <div className="steps-grid">
            {steps.map((step, index) => (
              <article className="step-item" key={step.title}>
                <span aria-hidden="true">{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="section" aria-labelledby="principles-title">
          <div className="section__header">
            <div>
              <h2 id="principles-title">Trust and responsibility</h2>
            </div>
          </div>
          <div className="trust-strip">
            {trustPrinciples.map((principle) => (
              <div className="trust-item" key={principle}>
                {principle}
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
