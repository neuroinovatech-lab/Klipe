// custos.js — quanto cada uso pago custou, medido e anotado.
//
// Duas decisoes que valem explicar, porque mudam a confianca no numero:
//
// 1. A QUANTIDADE e medida, a TARIFA e sua.
//    O Klipe sabe exatamente quantos segundos de video foram gerados ou
//    enviados - isso ele conta. Quanto o Google cobra por segundo muda com
//    o tempo, o modelo e a regiao, e um valor errado mostrado com confianca
//    e pior que valor nenhum: leva a decisao errada e ninguem desconfia.
//    Por isso a tarifa fica em Configuracoes, editavel, com a data em que
//    foi conferida. Os padroes abaixo sao ponto de partida, nao verdade.
//
// 2. O registro e JSONL, uma linha por uso.
//    Anexar linha nunca corrompe o arquivo. Um JSON unico reescrito a cada
//    uso perde tudo se o processo morrer no meio da escrita - e render longo
//    e exatamente onde as coisas morrem no meio.
//
// Mora no perfil do usuario, junto das chaves: e gasto DELE, e nao pode
// viajar quando a pasta do projeto for copiada para outro PC.

const fs = require("fs");
const os = require("os");
const path = require("path");

const PASTA = path.join(process.env.LOCALAPPDATA || os.homedir(), "Klipe");
const LIVRO = path.join(PASTA, "gastos.jsonl");

// Ponto de partida em US$. Conferir em ai.google.dev/pricing e ajustar em
// Configuracoes - o Klipe nao tem como saber o preco de hoje sozinho.
const TARIFAS_PADRAO = {
  tarifa_veo_seg: 0.40,    // por segundo de video GERADO
  tarifa_omni_seg: 0.30,   // por segundo de video ENVIADO para edicao
  tarifa_gemini_mtok_in: 0.10,   // por MILHAO de tokens de entrada
  tarifa_gemini_mtok_out: 0.40,  // por MILHAO de tokens de saida
};

// O Veo 3.1 entrega clipe de 8s quando nada e pedido em contrario. Nao ha
// campo de duracao na requisicao que o Klipe faz, entao e isso que cobra.
const VEO_SEG_PADRAO = 8;

function tarifa(nome, ajustes) {
  const v = Number(ajustes && ajustes[nome]);
  return Number.isFinite(v) && v >= 0 ? v : TARIFAS_PADRAO[nome];
}

/** Anota um uso pago e devolve o que ele custou. Nunca lanca: falhar em
 *  gravar o registro nao pode derrubar o render que a pessoa esta fazendo. */
function registrar({ tipo, modelo, segundos, tokensEntrada, tokensSaida, projeto, ajustes }) {
  try {
    const seg = Number(segundos) || 0;
    // Video cobra por segundo; texto cobra por token, e por isso entrada e
    // saida tem preco diferente. Um so caminho de calculo esconderia isso.
    let t = 0, custo = 0;
    if (tipo === "gemini") {
      const ent = Number(tokensEntrada) || 0;
      const sai = Number(tokensSaida) || 0;
      custo = (ent / 1e6) * tarifa("tarifa_gemini_mtok_in", ajustes)
            + (sai / 1e6) * tarifa("tarifa_gemini_mtok_out", ajustes);
    } else {
      t = tarifa(tipo === "veo" ? "tarifa_veo_seg" : "tarifa_omni_seg", ajustes);
      custo = seg * t;
    }
    const linha = {
      quando: new Date().toISOString(),
      tipo,
      modelo: modelo || "",
      segundos: seg,
      tokensEntrada: Number(tokensEntrada) || 0,
      tokensSaida: Number(tokensSaida) || 0,
      tarifa: t,
      custo: Number(custo.toFixed(4)),
      moeda: "USD",
      projeto: projeto || "",
    };
    fs.mkdirSync(PASTA, { recursive: true });
    fs.appendFileSync(LIVRO, JSON.stringify(linha) + "\n", "utf8");
    return linha;
  } catch (e) {
    console.log(`[custos] nao consegui anotar (${e.message})`);
    return null;
  }
}

function _linhas() {
  try {
    return fs.readFileSync(LIVRO, "utf8")
      .split("\n")
      .filter(Boolean)
      .map((l) => { try { return JSON.parse(l); } catch { return null; } })
      .filter(Boolean);
  } catch {
    return [];
  }
}

/** Total, quebra por tipo e os ultimos usos, para a tela. */
function resumo(limite = 30) {
  const L = _linhas();
  const desde = new Date(Date.now() - 30 * 864e5).toISOString();
  const soma = (arr) => arr.reduce((s, x) => s + (x.custo || 0), 0);
  const porTipo = {};
  for (const l of L) {
    porTipo[l.tipo] = porTipo[l.tipo] || { usos: 0, segundos: 0, custo: 0 };
    porTipo[l.tipo].usos += 1;
    porTipo[l.tipo].segundos += l.segundos || 0;
    porTipo[l.tipo].custo += l.custo || 0;
  }
  for (const k of Object.keys(porTipo)) porTipo[k].custo = Number(porTipo[k].custo.toFixed(2));
  return {
    total: Number(soma(L).toFixed(2)),
    mes: Number(soma(L.filter((l) => l.quando >= desde)).toFixed(2)),
    usos: L.length,
    porTipo,
    ultimos: L.slice(-limite).reverse(),
    arquivo: LIVRO,
    padroes: TARIFAS_PADRAO,
  };
}

module.exports = { registrar, resumo, TARIFAS_PADRAO, VEO_SEG_PADRAO, LIVRO };
