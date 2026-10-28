// Brand kit downloads (decision 064): a card per logo file, with its SVG and PNG under static/brand/.
import React from "react";
import Translate, { translate } from "@docusaurus/Translate";
import useBaseUrl from "@docusaurus/useBaseUrl";
import estilos from "./styles.module.css";

// A function, so the titles are translated when the page renders.
const arquivos = () => [
  {
    nome: "kaladrius-logo",
    titulo: translate({ id: "marca.logo", message: "Logo" }),
    fundo: "claro",
  },
  {
    nome: "kaladrius-logo-white",
    titulo: translate({ id: "marca.logoBranco", message: "Logo, white" }),
    fundo: "escuro",
  },
  {
    nome: "kaladrius-logo-black",
    titulo: translate({ id: "marca.logoPreto", message: "Logo, black" }),
    fundo: "claro",
  },
  {
    nome: "kaladrius-symbol",
    titulo: translate({ id: "marca.simbolo", message: "Symbol" }),
    fundo: "claro",
  },
  {
    nome: "kaladrius-symbol-white",
    titulo: translate({ id: "marca.simboloBranco", message: "Symbol, white" }),
    fundo: "escuro",
  },
  {
    nome: "kaladrius-symbol-black",
    titulo: translate({ id: "marca.simboloPreto", message: "Symbol, black" }),
    fundo: "claro",
  },
  {
    nome: "kaladrius-icon",
    titulo: translate({ id: "marca.icone", message: "App icon" }),
    fundo: "claro",
  },
];

function Cartao({ nome, titulo, fundo }) {
  const svg = useBaseUrl(`/brand/${nome}.svg`);
  const png = useBaseUrl(`/brand/${nome}.png`);
  return (
    <div className={estilos.cartao}>
      <div className={`${estilos.previa} ${estilos[fundo]}`}>
        <img src={svg} alt={titulo} />
      </div>
      <div className={estilos.rodape}>
        <strong>{titulo}</strong>
        <span className={estilos.botoes}>
          <a className="button button--sm button--outline button--primary" href={svg} download>
            SVG
          </a>
          <a className="button button--sm button--outline button--primary" href={png} download>
            PNG
          </a>
        </span>
      </div>
    </div>
  );
}

export default function KitDeMarca() {
  return (
    <>
      <p>
        <a className="button button--primary" href={useBaseUrl("/brand/kaladrius-brand-kit.zip")} download>
          <Translate id="marca.baixarTudo">Download everything (.zip)</Translate>
        </a>
      </p>
      <div className={estilos.grade}>
        {arquivos().map((arquivo) => (
          <Cartao key={arquivo.nome} {...arquivo} />
        ))}
      </div>
    </>
  );
}

export function Cor({ nome, hex }) {
  return (
    <div className={estilos.cor}>
      <span className={estilos.amostra} style={{ background: hex }} />
      <span>
        <strong>{nome}</strong>
        <br />
        <code>{hex}</code>
      </span>
    </div>
  );
}
