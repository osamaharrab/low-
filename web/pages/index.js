import Head from "next/head";

import AppShell from "../components/AppShell";
import CapabilityCard from "../components/CapabilityCard";
import HomeHero from "../components/HomeHero";
import HowItWorks from "../components/HowItWorks";
import TopicGrid from "../components/TopicGrid";
import TrustPanel from "../components/TrustPanel";

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

      <HomeHero />

      <div className="home-panel">
        <section className="section" aria-labelledby="capabilities-title">
          <div className="section__header">
            <div>
              <p className="section-kicker">Core capabilities</p>
              <h2 id="capabilities-title">Choose a legal research path</h2>
              <p>
                Both tools are part of the same Lawz AI JO platform and are designed for different Jordanian labour-law
                research workflows.
              </p>
            </div>
          </div>
          <div className="capability-grid">
            {capabilities.map((capability) => (
              <CapabilityCard key={capability.href} {...capability} />
            ))}
          </div>
        </section>

        <section className="home-grid-section">
          <HowItWorks />
          <TrustPanel />
        </section>

        <TopicGrid />
      </div>
    </AppShell>
  );
}
