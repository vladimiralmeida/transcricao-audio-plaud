/* Transcrição de áudio do Plaud Note Pro — painel local · Vladimir Almeida */
'use strict';

// ------------------------------------------------------------------ utilitários
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function api(url, opts = {}) {
  const init = { ...opts };
  if (init.json !== undefined) {
    init.method = init.method || 'POST';
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(init.json);
  }
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = r.statusText;
    try { const d = await r.json(); msg = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail); } catch { /* sem corpo */ }
    throw new Error(msg);
  }
  return r.headers.get('content-type')?.includes('json') ? r.json() : r;
}

function toast(msg, erro = false) {
  const el = document.createElement('div');
  el.className = 'toast' + (erro ? ' err' : '');
  el.textContent = msg;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), erro ? 7000 : 3800);
}
const falha = e => toast(e.message || String(e), true);

const hms = s => { s = Math.max(0, Math.floor(s || 0)); return [s / 3600 | 0, (s % 3600) / 60 | 0, s % 60].map(n => String(n).padStart(2, '0')).join(':'); };
const dur = s => { s = Math.round(s || 0); const h = s / 3600 | 0, m = (s % 3600) / 60 | 0; return h ? `${h} h ${m} min` : m ? `${m} min` : `${s} s`; };
const quando = iso => iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '';
const mb = n => (n / 1048576).toFixed(1).replace('.', ',') + ' MB';
const gb = mib => (mib / 1024).toFixed(1).replace('.', ',');

function md(src) {
  const inline = t => t.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*/g, '$1<i>$2</i>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const out = []; let lista = null;
  const fecha = () => { if (lista) { out.push(`</${lista}>`); lista = null; } };
  for (const raw of esc(src || '').split('\n')) {
    const l = raw.trimEnd(); let m;
    if ((m = l.match(/^(#{1,4})\s+(.*)/))) { fecha(); out.push(`<h${Math.min(m[1].length + 1, 4)}>${inline(m[2])}</h${Math.min(m[1].length + 1, 4)}>`); }
    else if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { if (lista !== 'ul') { fecha(); out.push('<ul>'); lista = 'ul'; } out.push(`<li>${inline(m[1])}</li>`); }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { if (lista !== 'ol') { fecha(); out.push('<ol>'); lista = 'ol'; } out.push(`<li>${inline(m[1])}</li>`); }
    else if (!l.trim()) fecha();
    else { fecha(); out.push(`<p>${inline(l)}</p>`); }
  }
  fecha();
  return out.join('');
}

async function copiar(texto) {
  try { await navigator.clipboard.writeText(texto); }
  catch { const t = document.createElement('textarea'); t.value = texto; document.body.append(t); t.select(); document.execCommand('copy'); t.remove(); }
}

// ------------------------------------------------------------------------ ícones
const I = {
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg>',
  file: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>',
  down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v12m0 0 5-5m-5 5-5-5M5 20h14"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21a2 2 0 0 1 2-2h13"/></svg>',
  orientacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m2 9 10-5 10 5-10 5z"/><path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5"/></svg>',
  entrevista: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  reuniao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18"/></svg>',
  aula: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
};
const ORDEM = ['orientacao', 'entrevista', 'reuniao', 'aula'];
const CORES = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6', '#ef4444', '#84cc16'];
const corDe = (rotulos, r) => CORES[Math.max(0, rotulos.indexOf(r)) % CORES.length];
const PILULA = { fila: ['warn', 'Na fila'], processando: ['run', 'Processando'], concluido: ['ok', 'Concluído'], erro: ['err', 'Erro'], cancelado: ['', 'Cancelado'] };
const pilula = s => { const [c, t] = PILULA[s] || ['', s]; return `<span class="pill ${c}"><span class="dot"></span>${t}</span>`; };

// ------------------------------------------------------------------------ estado
const S = {
  estado: null, ativos: [], gpu: [], fila: 0, versao: -1, prog: {},
  rota: null, job: null, dirty: false, aba: 'transcricao',
  home: { perfil: 'orientacao', arquivo: null, n: 0, pessoas: [] },
  hist: { q: '', perfil: '' },
};
const ativoAgora = () => S.ativos.find(a => a.estado === 'processando') || null;

// -------------------------------------------------------------------- tema (opcional)
function aplicarTema(t) { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; }
try { aplicarTema(localStorage.getItem('tema')); } catch { /* sem armazenamento */ }
$('#tema').onclick = () => {
  const escuro = getComputedStyle(document.documentElement).colorScheme === 'dark';
  const novo = escuro ? 'light' : 'dark';
  aplicarTema(novo);
  try { localStorage.setItem('tema', novo); } catch { /* ignora */ }
};

// ----------------------------------------------------------- gráficos (SVG à mão)
const RAIO = 62, CIRC = 2 * Math.PI * RAIO;

function ringHTML(id, pct, centro, sub, idle) {
  return `<div class="ring ${idle ? 'idle' : ''}" id="${id}">
    <svg viewBox="0 0 148 148"><defs><linearGradient id="gring-${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--accent)"/><stop offset="1" stop-color="var(--accent-2)"/></linearGradient></defs>
      <circle class="trk" cx="74" cy="74" r="${RAIO}" fill="none" stroke-width="11"/>
      <circle class="val" cx="74" cy="74" r="${RAIO}" fill="none" stroke-width="11" stroke-linecap="round" style="stroke:url(#gring-${id})"
        stroke-dasharray="${CIRC.toFixed(1)}" stroke-dashoffset="${(CIRC * (1 - pct / 100)).toFixed(1)}"/></svg>
    <div class="mid"><div><b>${centro}</b><br><small>${sub}</small></div></div></div>`;
}
function setRing(id, pct, centro, sub, idle) {
  const el = document.getElementById(id); if (!el) return;
  el.classList.toggle('idle', !!idle);
  $('.val', el).style.strokeDashoffset = (CIRC * (1 - pct / 100)).toFixed(1);
  $('.mid b', el).textContent = centro; $('.mid small', el).textContent = sub;
}

/** Gráfico de área em SVG. pontos: [[x(0..1), y(0..1)]], série opcional tracejada. */
function areaChart({ id, cor, corSoft, rotulosY, janela }) {
  const W = 560, H = 150;
  return `<svg id="${id}" viewBox="0 0 ${W + 44} ${H + 8}" preserveAspectRatio="none" style="height:${H + 8}px">
    <defs><linearGradient id="${id}-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${cor}" stop-opacity=".45"/><stop offset="1" stop-color="${cor}" stop-opacity=".02"/></linearGradient></defs>
    <g class="grid">${[0, .25, .5, .75, 1].map(f => `<line x1="0" x2="${W}" y1="${(4 + H * (1 - f)).toFixed(1)}" y2="${(4 + H * (1 - f)).toFixed(1)}"/>`).join('')}</g>
    <g class="ylab">${rotulosY.map(([f, t]) => `<text class="lbl" x="${W + 6}" y="${(8 + H * (1 - f)).toFixed(1)}">${t}</text>`).join('')}</g>
    <path class="area" fill="url(#${id}-g)" d=""/><path class="line" fill="none" stroke="${cor}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" d=""/>
    <path class="line2" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="4 4" opacity=".7" d=""/>
    <circle class="head" r="4.5" fill="${cor}" stroke="var(--surface)" stroke-width="2" cx="-10" cy="-10"/></svg>`;
}
function desenhar(id, pts, pts2) {
  const svg = document.getElementById(id); if (!svg) return;
  const W = 560, H = 150;
  const xy = ([x, y]) => `${(x * W).toFixed(1)},${(4 + H * (1 - y)).toFixed(1)}`;
  const linha = p => p.length ? 'M' + p.map(xy).join(' L') : '';
  $('.line', svg).setAttribute('d', linha(pts));
  $('.area', svg).setAttribute('d', pts.length ? `M${(pts[0][0] * W).toFixed(1)},${4 + H} L${pts.map(xy).join(' L')} L${(pts[pts.length - 1][0] * W).toFixed(1)},${4 + H} Z` : '');
  $('.line2', svg).setAttribute('d', pts2 ? linha(pts2) : '');
  const head = $('.head', svg);
  if (pts.length) { const [x, y] = pts[pts.length - 1]; head.setAttribute('cx', (x * W).toFixed(1)); head.setAttribute('cy', (4 + H * (1 - y)).toFixed(1)); }
}

// ----------------------------------------------------------------- monitor (GPU)
const JANELA_S = 120;
function monitorHTML() {
  return `<div class="card monitor">
    <div class="card-head"><div><h2>Painel da GPU</h2><div class="muted small" id="gpunome">${esc(S.estado?.gpu_nome || 'NVIDIA GPU')}</div></div>
      <div class="legend"><span><i style="background:var(--vram)"></i>VRAM</span><span><i style="background:var(--accent)"></i>Uso da GPU</span></div></div>
    <div class="chart" id="vramwrap">${areaChart({ id: 'vramchart', cor: 'var(--vram)', rotulosY: [[0, '0'], [.5, '3'], [1, '6 GB']] })}</div>
    <div class="stats">
      <div class="stat"><small>VRAM em uso</small><b id="s-vram">–</b></div>
      <div class="stat"><small>Uso da GPU</small><b id="s-util">–</b></div>
      <div class="stat"><small>Temperatura</small><b id="s-temp">–</b></div>
    </div>
    <div class="card-head" style="margin:6px 0 -4px"><h2>Evolução da transcrição</h2><span class="muted small" id="eta"></span></div>
    <div class="live">
      ${ringHTML('mring', 0, '–', 'ocioso', true)}
      <div class="chart" id="progwrap">${areaChart({ id: 'progchart', cor: 'var(--accent)', rotulosY: [[0, '0%'], [.5, '50%'], [1, '100%']] })}</div>
    </div>
    <div id="etapa" class="muted small" style="text-align:center"></div>
    <div class="queue" id="queue"></div>
  </div>`;
}

function atualizarMonitor() {
  if (!$('#vramchart')) return;
  const total = S.estado?.gpu_total_mib || 6144, agora = Date.now() / 1000;
  const pts = S.gpu.filter(g => agora - g.t <= JANELA_S).map(g => [1 - (agora - g.t) / JANELA_S, Math.min(g.usada / g.total, 1)]);
  const pu = S.gpu.filter(g => agora - g.t <= JANELA_S).map(g => [1 - (agora - g.t) / JANELA_S, g.util / 100]);
  desenhar('vramchart', pts, pu);
  const u = S.gpu[S.gpu.length - 1];
  if (u) {
    $('#s-vram').innerHTML = `${gb(u.usada)}<em> / ${gb(u.total)} GB</em>`;
    $('#s-util').innerHTML = `${u.util}<em> %</em>`;
    $('#s-temp').innerHTML = `${u.temp}<em> °C</em>`;
  }
  const a = ativoAgora();
  if (a) {
    const h = S.prog[a.id] || [];
    const t0 = h.length ? h[0][0] : Date.now() / 1000, t1 = Date.now() / 1000;
    const pg = h.map(([t, p]) => [Math.min((t - t0) / Math.max(t1 - t0, 30), 1), p / 100]);
    desenhar('progchart', pg);
    setRing('mring', a.progresso, `${Math.floor(a.progresso)}%`, a.tipo === 'c' ? 'documento' : 'transcrevendo', false);
    $('#etapa').textContent = `${a.etapa} · ${a.nome}`;
    $('#eta').textContent = estimar(h);
  } else {
    desenhar('progchart', []);
    setRing('mring', 0, '–', 'ocioso', true);
    $('#etapa').textContent = S.fila ? 'Aguardando a fila…' : 'Nenhum trabalho em andamento. Envie um áudio para começar.';
    $('#eta').textContent = '';
  }
  $('#queue').innerHTML = S.ativos.map(x => `<div class="qitem"><div class="ellipsis"><b>${esc(x.nome)}</b>
      <span class="muted small"> · ${esc(S.estado?.perfis?.[x.perfil]?.nome || x.perfil)} · ${esc(x.estado === 'fila' ? 'na fila' : x.etapa)}</span></div>
      <div class="row"><b class="mono">${Math.floor(x.progresso)}%</b><button class="btn sm danger" data-cancelar="${x.id}" data-tipo="${x.tipo}">Cancelar</button></div>
      <div class="bar"><i style="width:${x.progresso}%"></i></div></div>`).join('');
}

function estimar(h) {
  if (h.length < 3) return '';
  const fim = h[h.length - 1], ref = h.find(p => fim[0] - p[0] <= 40) || h[0];
  const dp = fim[1] - ref[1], dt = fim[0] - ref[0];
  if (dp <= 0.2 || dt < 5) return '';
  const resta = (100 - fim[1]) / (dp / dt);
  return `≈ ${dur(resta)} restantes (estimativa)`;
}

// ------------------------------------------------------------------ fluxo (SSE)
function conectar() {
  const es = new EventSource('/api/stream');
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.gpu) { if (!S.gpu.length || S.gpu[S.gpu.length - 1].t !== d.gpu.t) S.gpu.push(d.gpu); S.gpu = S.gpu.slice(-JANELA_S - 10); }
    S.ativos = d.ativos; S.fila = d.fila;
    for (const a of d.ativos) {
      if (a.estado !== 'processando') continue;
      const h = S.prog[a.id] = S.prog[a.id] || [];
      if (!h.length || h[h.length - 1][1] !== a.progresso) h.push([d.t, a.progresso]);
    }
    const n = d.ativos.length;
    $('#navcount').textContent = n; $('#navcount').classList.toggle('hidden', !n);
    if (d.versao !== S.versao) { S.versao = d.versao; aoMudar(); }
    atualizarMonitor(); atualizarJobAoVivo();
  };
  es.onerror = () => { /* o navegador reconecta sozinho */ };
}
function aoMudar() {
  if (S.rota === 'home') carregarRecentes();
  else if (S.rota === 'historico') carregarHistorico();
  else if (S.rota === 'job' && S.job && !S.dirty) renderJob(S.job.id, true);
}

// --------------------------------------------------------------------- roteador
const view = $('#view');
function rota() {
  const h = location.hash.replace(/^#/, '') || '/';
  const partes = h.split('/').filter(Boolean);
  let r = partes[0] || 'home';
  if (!['home', 'historico', 'job', 'config'].includes(r)) r = 'home';
  if (S.dirty && !confirm('Há alterações não salvas. Sair mesmo assim?')) { history.back(); return; }
  S.dirty = false; S.rota = r;
  $$('#nav a').forEach(a => a.classList.toggle('on', a.dataset.r === (r === 'job' ? 'historico' : r)));
  window.scrollTo(0, 0);
  ({ home: renderHome, historico: renderHistorico, job: () => renderJob(+partes[1]), config: renderConfig })[r]();
}
window.addEventListener('hashchange', rota);

// ------------------------------------------------------------------------ início
function renderHome() {
  const e = S.estado, h = S.home;
  view.innerHTML = `
  <div class="page-head"><div><h1>Nova transcrição</h1><p>Transcreva localmente, identifique quem falou e gere o documento do perfil escolhido.</p></div></div>
  <div class="grid-home">
    <section class="card" id="novo">
      <div class="step"><i>1</i><h3>Perfil da gravação</h3></div>
      <div class="perfis">${ORDEM.map(k => `<button type="button" class="perfil ${h.perfil === k ? 'on' : ''}" data-perfil="${k}">
        <div class="ico">${I[k]}</div><b>${esc(e.perfis[k].nome)}</b><span>${esc(e.perfis[k].descricao)}</span></button>`).join('')}</div>
      <div class="step"><i>2</i><h3>Arquivo de áudio</h3></div>
      <div class="drop" id="drop" tabindex="0">
        ${h.arquivo ? `<div class="file">${I.file}<span>${esc(h.arquivo.name)}</span><span class="muted small">${mb(h.arquivo.size)}</span></div><div class="muted small" style="margin-top:6px">Clique para trocar</div>`
          : `${I.upload}<div style="margin-top:6px"><b>Arraste o áudio aqui</b> ou clique para escolher</div><div class="muted small">MP3, WAV, M4A e outros formatos do Plaud</div>`}
        <input type="file" id="arq" accept="audio/*,.mp3,.wav,.m4a,.flac,.ogg,.opus,.aac,.mp4,.webm" class="hidden">
      </div>
      <div class="muted small" style="margin-top:10px">Ou solte o arquivo na pasta monitorada
        <span class="kbd">entrada\\${h.perfil}</span> e ele será processado sozinho.
        <button class="btn sm ghost" id="abrirpasta">${I.folder} Abrir pasta</button></div>
      <div class="step"><i>3</i><h3>Falantes</h3></div>
      <div class="row"><span class="muted small">Quantas pessoas falam?</span>
        <div class="stepper"><button type="button" data-n="-1" aria-label="Menos">−</button><span>${h.n ? h.n : 'Automático'}</span><button type="button" data-n="1" aria-label="Mais">+</button></div></div>
      <div class="people" id="people">${h.n ? Array.from({ length: h.n }, (_, i) => {
          const p = h.pessoas[i] || {};
          return `<div class="person"><span class="n">${i + 1}</span><input type="text" data-p="${i}" data-k="nome" placeholder="Nome (opcional)" value="${esc(p.nome || '')}">
          <input type="text" data-p="${i}" data-k="papel" list="papeis" placeholder="Papel" value="${esc(p.papel || '')}"></div>`;
        }).join('') : '<div class="muted small">No modo automático o app detecta o número de vozes. Você poderá dar nome a cada uma depois, ouvindo exemplos.</div>'}</div>
      <datalist id="papeis">${e.perfis[h.perfil].papeis.map(p => `<option value="${esc(p)}">`).join('')}</datalist>
      <div class="row" style="margin-top:24px"><button class="btn primary" id="enviar" ${h.arquivo ? '' : 'disabled'}>${I.spark} Iniciar transcrição</button>
        <div class="bar hidden" id="upbar" style="flex:1"><i style="width:0"></i></div><span class="muted small" id="uptxt"></span></div>
    </section>
    <div>${monitorHTML()}</div>
  </div>
  <section class="card" style="margin-top:22px"><div class="card-head"><h2>Recentes</h2><a class="btn sm ghost" href="#/historico">Ver tudo</a></div><div class="list" id="recentes"></div></section>`;

  $$('.perfil').forEach(b => b.onclick = () => { h.perfil = b.dataset.perfil; renderHome(); });
  const drop = $('#drop'), arq = $('#arq');
  drop.onclick = () => arq.click();
  drop.onkeydown = ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); arq.click(); } };
  arq.onclick = ev => ev.stopPropagation();
  arq.onchange = () => { if (arq.files[0]) { h.arquivo = arq.files[0]; renderHome(); } };
  ['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, ev => { ev.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(t => drop.addEventListener(t, ev => { ev.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', ev => { const f = ev.dataTransfer.files[0]; if (f) { h.arquivo = f; renderHome(); } });
  $$('.stepper button').forEach(b => b.onclick = () => { h.n = Math.max(0, Math.min(8, h.n + +b.dataset.n)); renderHome(); });
  $$('#people input').forEach(i => i.oninput = () => { (h.pessoas[+i.dataset.p] ||= {})[i.dataset.k] = i.value; });
  $('#abrirpasta').onclick = () => api('/api/abrir-pasta', { json: { qual: `entrada/${h.perfil}` } }).catch(falha);
  $('#enviar').onclick = enviar;
  atualizarMonitor(); carregarRecentes();
}

function enviar() {
  const h = S.home, fd = new FormData();
  fd.append('arquivo', h.arquivo); fd.append('perfil', h.perfil);
  fd.append('num_falantes', h.n ? String(h.n) : 'auto');
  fd.append('participantes', JSON.stringify(h.n ? Array.from({ length: h.n }, (_, i) => h.pessoas[i] || {}) : []));
  const xhr = new XMLHttpRequest();
  $('#enviar').disabled = true; $('#upbar').classList.remove('hidden');
  xhr.upload.onprogress = ev => { if (ev.lengthComputable) { $('#upbar i').style.width = (100 * ev.loaded / ev.total) + '%'; $('#uptxt').textContent = `Enviando ${Math.floor(100 * ev.loaded / ev.total)}%`; } };
  xhr.onload = () => {
    if (xhr.status === 200) {
      const id = JSON.parse(xhr.responseText).id;
      toast('Áudio enviado. A transcrição começou.');
      S.home = { perfil: h.perfil, arquivo: null, n: 0, pessoas: [] };
      S.prog = {}; renderHome();
      void id;
    } else { let m = 'Falha no envio.'; try { m = JSON.parse(xhr.responseText).detail || m; } catch { /* ok */ } falha(new Error(m)); $('#enviar').disabled = false; }
  };
  xhr.onerror = () => { falha(new Error('Falha de rede no envio.')); $('#enviar').disabled = false; };
  xhr.open('POST', '/api/jobs'); xhr.send(fd);
}

const itemHTML = j => `<a class="item" href="#/job/${j.id}">
  <div class="ico">${I[j.perfil] || I.doc}</div>
  <div style="min-width:0"><div class="ellipsis"><b>${esc(j.nome)}</b></div>
    <div class="meta"><span>${esc(S.estado.perfis[j.perfil]?.nome || j.perfil)}</span><span>${quando(j.criado_em)}</span>${j.duracao ? `<span>${dur(j.duracao)}</span>` : ''}
    ${j.origem === 'pasta' ? '<span>pasta monitorada</span>' : ''}${j.ctx_status === 'pronto' ? '<span style="color:var(--ok)">documento gerado</span>' : ''}</div></div>
  <div>${pilula(j.status)}</div></a>`;
const vazio = txt => `<div class="empty">${I.search}<div style="margin-top:8px">${txt}</div></div>`;

async function carregarRecentes() {
  const el = $('#recentes'); if (!el) return;
  try { const l = (await api('/api/jobs')).slice(0, 5); el.innerHTML = l.length ? l.map(itemHTML).join('') : vazio('Nenhuma transcrição ainda.'); } catch (e) { falha(e); }
}

// -------------------------------------------------------------------- histórico
function renderHistorico() {
  const e = S.estado;
  view.innerHTML = `<div class="page-head"><div><h1>Histórico e busca</h1><p>Pesquise em todo o texto das transcrições e dos documentos gerados.</p></div></div>
    <div class="toolbar"><div class="search">${I.search}<input type="search" id="q" placeholder="Buscar palavras ditas, nomes, assuntos…" value="${esc(S.hist.q)}"></div>
    <div class="chips"><button class="chip ${S.hist.perfil ? '' : 'on'}" data-p="">Todos</button>${ORDEM.map(k => `<button class="chip ${S.hist.perfil === k ? 'on' : ''}" data-p="${k}">${esc(e.perfis[k].nome)}</button>`).join('')}</div></div>
    <div class="list" id="lista"></div>`;
  let t; $('#q').oninput = ev => { clearTimeout(t); t = setTimeout(() => { S.hist.q = ev.target.value; carregarHistorico(); }, 250); };
  $$('.chip').forEach(c => c.onclick = () => { S.hist.perfil = c.dataset.p; renderHistorico(); });
  carregarHistorico();
}
async function carregarHistorico() {
  const el = $('#lista'); if (!el) return;
  try {
    const l = await api(`/api/jobs?q=${encodeURIComponent(S.hist.q)}&perfil=${S.hist.perfil}`);
    el.innerHTML = l.length ? l.map(itemHTML).join('') : vazio(S.hist.q ? 'Nada encontrado para essa busca.' : 'Nenhuma transcrição ainda.');
  } catch (e) { falha(e); }
}

// ----------------------------------------------------------------------- detalhe
async function renderJob(id, silencioso = false) {
  if (!id) { location.hash = '#/historico'; return; }
  let j;
  try { j = await api(`/api/jobs/${id}`); } catch (e) { falha(e); location.hash = '#/historico'; return; }
  if (S.rota !== 'job') return;
  const prev = S.job; S.job = j;
  if (silencioso && prev && prev.id === j.id && prev.status === 'concluido' && j.status === 'concluido' && prev.ctx_status === j.ctx_status && $('#jbody')) {
    return; // nada visível mudou; evita redesenhar e perder a posição de rolagem/edição
  }
  const e = S.estado, p = e.perfis[j.perfil];
  const rot = rotulosDe(j);
  view.innerHTML = `
    <div class="page-head"><div style="min-width:0"><a class="muted small" href="#/historico">← Histórico</a>
      <h1 class="ellipsis" style="margin-top:4px">${esc(j.nome)}</h1>
      <p class="row" style="gap:8px">${pilula(j.status)}<span>${esc(p.nome)}</span><span>·</span><span>${quando(j.criado_em)}</span>${j.duracao ? `<span>·</span><span>${dur(j.duracao)}</span>` : ''}${rot.length ? `<span>·</span><span>${rot.length} falante${rot.length > 1 ? 's' : ''}</span>` : ''}</p></div>
      <div class="row">${['erro', 'cancelado', 'concluido'].includes(j.status) ? '<button class="btn sm" id="reproc">Reprocessar</button>' : ''}
        ${!j.ativo ? '<button class="btn sm danger" id="remover">Remover do histórico</button>' : ''}</div></div>
    <div id="jbody"></div>`;
  $('#reproc')?.addEventListener('click', async () => { if (confirm('Refazer a transcrição deste áudio? A edição atual será substituída.')) { try { await api(`/api/jobs/${j.id}/reprocessar`, { method: 'POST' }); toast('Reprocessamento iniciado.'); } catch (x) { falha(x); } } });
  $('#remover')?.addEventListener('click', async () => {
    if (!confirm('Remover do histórico do painel? O arquivo .md e o áudio permanecem nas pastas.')) return;
    try { await api(`/api/jobs/${j.id}`, { method: 'DELETE' }); location.hash = '#/historico'; } catch (x) { falha(x); }
  });
  const corpo = $('#jbody');
  if (j.status === 'fila' || j.status === 'processando') {
    corpo.innerHTML = `<div class="card" style="max-width:560px"><div class="live">${ringHTML('jring', 0, '0%', 'processando')}
      <div><h2 id="jetapa">Na fila…</h2><p class="muted small" id="jeta"></p><div class="chart" id="jprogwrap">${areaChart({ id: 'jprog', cor: 'var(--accent)', rotulosY: [[0, '0%'], [1, '100%']] })}</div>
      <button class="btn sm danger" id="cancelar">Cancelar</button></div></div></div>`;
    $('#cancelar').onclick = () => api(`/api/jobs/${j.id}/cancelar`, { json: { tipo: 't' } }).catch(falha);
    atualizarJobAoVivo();
  } else if (j.status === 'erro') {
    corpo.innerHTML = `<div class="callout err"><b>A transcrição falhou.</b><br>${esc(j.erro || '')}<br><span class="small">Detalhes técnicos (sem trechos da fala) ficam em erros\\${esc(j.perfil)}.</span></div>`;
  } else if (j.status === 'cancelado') {
    corpo.innerHTML = '<div class="callout info">Este trabalho foi cancelado. Use “Reprocessar” para tentar de novo.</div>';
  } else {
    corpo.innerHTML = `<div class="tabs" id="tabs">${[['transcricao', 'Transcrição'], ['falantes', 'Falantes'], ['documento', p.documento], ['exportar', 'Exportar']]
      .map(([k, t]) => `<button class="tab ${S.aba === k ? 'on' : ''}" data-aba="${k}">${esc(t)}</button>`).join('')}</div><div id="aba"></div>`;
    $$('.tab').forEach(t => t.onclick = () => { if (S.dirty && !confirm('Há alterações não salvas. Descartar?')) return; S.dirty = false; S.aba = t.dataset.aba; renderJob(j.id); });
    ({ transcricao: abaTranscricao, falantes: abaFalantes, documento: abaDocumento, exportar: abaExportar })[S.aba](j);
  }
}
function atualizarJobAoVivo() {
  if (S.rota !== 'job' || !S.job || !$('#jring')) return;
  const a = S.ativos.find(x => x.id === S.job.id);
  if (!a) return;
  setRing('jring', a.progresso, `${Math.floor(a.progresso)}%`, a.estado === 'fila' ? 'na fila' : 'processando');
  $('#jetapa').textContent = a.etapa;
  const h = S.prog[a.id] || [];
  $('#jeta').textContent = estimar(h);
  const t0 = h.length ? h[0][0] : 0, t1 = Date.now() / 1000;
  desenhar('jprog', h.map(([t, p]) => [Math.min((t - t0) / Math.max(t1 - t0, 30), 1), p / 100]));
}
const rotulosDe = j => { const r = []; for (const t of j.turnos || []) if (!r.includes(t.falante)) r.push(t.falante); return r; };
const nomeDe = (j, r) => j.falantes[r]?.nome || r;

// ---- aba: transcrição (editor sincronizado com o áudio)
function abaTranscricao(j) {
  const rot = rotulosDe(j);
  $('#aba').innerHTML = `
    <div class="player"><audio id="aud" controls preload="metadata" src="/api/jobs/${j.id}/audio"></audio>
      <select id="vel" style="width:auto" aria-label="Velocidade"><option value="0.75">0,75×</option><option value="1" selected>1×</option><option value="1.25">1,25×</option><option value="1.5">1,5×</option><option value="2">2×</option></select>
      <label class="row small muted" style="gap:6px"><input type="checkbox" id="seguir" checked> Acompanhar</label></div>
    <div id="turnos">${j.turnos.map((t, i) => `<div class="turn" data-i="${i}">
      <button class="t" data-ir="${i}" title="Ouvir a partir daqui">${hms(t.inicio)}</button>
      <div><div class="who"><span class="spk-dot" style="background:${corDe(rot, t.falante)}"></span>
        <select data-spk="${i}">${rot.map(r => `<option value="${esc(r)}" ${r === t.falante ? 'selected' : ''}>${esc(nomeDe(j, r))}${j.falantes[r]?.papel ? ' · ' + esc(j.falantes[r].papel) : ''}</option>`).join('')}</select></div>
        <textarea rows="1" data-txt="${i}" spellcheck="true">${esc(t.texto)}</textarea></div></div>`).join('') || vazio('Nenhuma fala detectada.')}</div>
    <div class="savebar hidden" id="savebar"><span>Alterações não salvas</span><div class="row"><button class="btn sm" id="descartar">Descartar</button><button class="btn sm primary" id="salvar">Salvar alterações</button></div></div>`;
  const aud = $('#aud'), turnos = j.turnos.map(t => ({ ...t }));
  const marcar = () => { S.dirty = true; $('#savebar').classList.remove('hidden'); };
  const auto = ta => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 2 + 'px'; };
  $$('textarea', $('#turnos')).forEach(ta => { auto(ta); ta.oninput = () => { turnos[+ta.dataset.txt].texto = ta.value; auto(ta); marcar(); }; });
  $$('select[data-spk]').forEach(s => s.onchange = () => { turnos[+s.dataset.spk].falante = s.value; s.previousElementSibling.style.background = corDe(rot, s.value); marcar(); });
  $$('[data-ir]').forEach(b => b.onclick = () => { aud.currentTime = turnos[+b.dataset.ir].inicio; aud.play(); });
  $('#vel').onchange = ev => aud.playbackRate = +ev.target.value;
  let atual = -1;
  aud.ontimeupdate = () => {
    const t = aud.currentTime; let i = turnos.findIndex((x, k) => x.inicio <= t && (k === turnos.length - 1 || turnos[k + 1].inicio > t));
    if (i === atual) return; atual = i;
    $$('.turn.now').forEach(x => x.classList.remove('now'));
    const el = $(`.turn[data-i="${i}"]`);
    if (el) { el.classList.add('now'); if ($('#seguir').checked) el.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
  };
  $('#salvar').onclick = async () => {
    try { await api(`/api/jobs/${j.id}/turnos`, { method: 'PUT', json: { turnos } }); S.dirty = false; toast('Transcrição salva.'); renderJob(j.id); } catch (e) { falha(e); }
  };
  $('#descartar').onclick = () => { S.dirty = false; renderJob(j.id); };
}

// ---- aba: falantes
function abaFalantes(j) {
  const e = S.estado, rot = rotulosDe(j), papeis = e.perfis[j.perfil].papeis, parts = (j.participantes || []).filter(p => p.nome || p.papel);
  const amostras = r => j.turnos.filter(t => t.falante === r && t.texto.length > 30).slice(0, 3);
  $('#aba').innerHTML = `<div class="card"><div class="card-head"><div><h2>Quem é cada voz?</h2>
      <div class="muted small">O app separa as vozes como “Falante 1, 2…”. Ouça os exemplos e informe nome e papel; o arquivo .md é atualizado ao salvar.</div></div></div>
    <datalist id="papeis">${papeis.map(p => `<option value="${esc(p)}">`).join('')}</datalist>
    <table class="table"><thead><tr><th>Voz</th><th>Exemplos (clique no tempo para ouvir)</th><th style="width:34%">Nome e papel</th></tr></thead><tbody>
    ${rot.map(r => `<tr data-r="${esc(r)}"><td><span class="spk-dot" style="background:${corDe(rot, r)}"></span> <b>${esc(r)}</b><div class="muted small">${j.turnos.filter(t => t.falante === r).length} falas</div></td>
      <td>${amostras(r).map(t => `<div class="sample"><button data-ouvir="${t.inicio}">${hms(t.inicio)}</button><span>${esc(t.texto.slice(0, 150))}${t.texto.length > 150 ? '…' : ''}</span></div>`).join('') || '<span class="muted small">Falas curtas.</span>'}</td>
      <td><div style="display:grid;gap:8px">
        ${parts.length ? `<select data-usar><option value="">Usar participante informado…</option>${parts.map((p, i) => `<option value="${i}">${esc(p.nome || '—')}${p.papel ? ' · ' + esc(p.papel) : ''}</option>`).join('')}</select>` : ''}
        <input type="text" data-nome placeholder="Nome" value="${esc(j.falantes[r]?.nome || '')}"><input type="text" data-papel list="papeis" placeholder="Papel" value="${esc(j.falantes[r]?.papel || '')}"></div></td></tr>`).join('')}
    </tbody></table><audio id="aud" preload="none" src="/api/jobs/${j.id}/audio"></audio>
    <div class="row" style="margin-top:16px"><button class="btn primary" id="salvarf">Salvar nomes e papéis</button></div></div>`;
  const aud = $('#aud');
  $$('[data-ouvir]').forEach(b => b.onclick = () => { aud.currentTime = +b.dataset.ouvir; aud.play(); setTimeout(() => aud.pause(), 9000); });
  $$('[data-usar]').forEach(s => s.onchange = () => { const p = parts[+s.value]; if (!p) return; const tr = s.closest('tr'); $('[data-nome]', tr).value = p.nome || ''; $('[data-papel]', tr).value = p.papel || ''; });
  $('#salvarf').onclick = async () => {
    const f = {}; $$('tbody tr').forEach(tr => { f[tr.dataset.r] = { nome: $('[data-nome]', tr).value, papel: $('[data-papel]', tr).value }; });
    try { await api(`/api/jobs/${j.id}/falantes`, { method: 'PUT', json: { falantes: f } }); toast('Falantes salvos.'); renderJob(j.id); } catch (x) { falha(x); }
  };
}

// ---- aba: documento contextualizado (LLM local) + prompt
function abaDocumento(j) {
  const e = S.estado, p = e.perfis[j.perfil], ent = j.perfil === 'entrevista', anon = j.anon || {};
  const gerando = ['fila', 'gerando'].includes(j.ctx_status), ativo = S.ativos.find(a => a.id === j.id && a.tipo === 'c');
  const oll = e.ollama, modelo = e.config.ollama_modelo;
  $('#aba').innerHTML = `
    <div class="card"><div class="card-head"><div><h2>${esc(p.documento)}</h2>
      <div class="muted small">Gerado a partir do texto bruto com o modelo local <span class="kbd">${esc(modelo)}</span>${oll.ativo ? '' : ' — <b style="color:var(--warn)">Ollama parado (será iniciado ao gerar)</b>'}.</div></div>
      <div class="row">${j.contexto && !gerando ? `<button class="btn sm" id="editar">Editar</button><button class="btn sm" id="copdoc">${I.copy} Copiar</button>` : ''}</div></div>
    ${ent ? '<div class="callout" style="margin-bottom:14px"><b>Entrevista de pesquisa — dado sensível.</b> O texto enviado ao modelo e o prompt para copiar usam sempre a versão <b>anonimizada</b>. Revise-a antes de usar fora deste computador.</div>' : ''}
    <div class="row" style="align-items:flex-start;margin-bottom:14px">
      <label class="row small" style="gap:8px"><input type="checkbox" id="anon" ${ent || anon.ativa ? 'checked' : ''} ${ent ? 'disabled' : ''}> Anonimizar nomes e dados pessoais</label></div>
    <label class="field hidden" id="termosw" style="margin-bottom:14px">Outros termos a anonimizar (um por linha: instituições, cidades, nomes de terceiros…)
      <textarea id="termos" rows="3" placeholder="Ex.: Universidade Federal de Pernambuco">${esc((anon.termos_extra || []).join('\n'))}</textarea></label>
    <div class="row"><button class="btn primary" id="gerar" ${gerando ? 'disabled' : ''}>${I.spark} ${j.contexto ? 'Gerar novamente' : 'Gerar com o LLM local'}</button>
      <button class="btn" id="copiarprompt">${I.copy} Copiar prompt para o Claude</button></div>
    <div id="ctxprog" class="${gerando ? '' : 'hidden'}" style="margin-top:16px"><div class="row small"><span id="ctxetapa">${esc(ativo?.etapa || 'Na fila…')}</span><b class="mono" id="ctxpct">${Math.floor(ativo?.progresso || 0)}%</b>
      <button class="btn sm danger" id="ctxcancel">Cancelar</button></div><div class="bar" style="margin-top:6px"><i id="ctxbar" style="width:${ativo?.progresso || 0}%"></i></div></div>
    ${j.ctx_status === 'erro' ? `<div class="callout err" style="margin-top:14px">${esc(j.ctx_erro || 'Falha ao gerar.')}</div>` : ''}
    </div>
    ${j.contexto ? `<div class="card"><div class="doc" id="docview">${md(j.contexto)}</div>
      <div class="hidden" id="docedit"><textarea id="doctxt" rows="22">${esc(j.contexto)}</textarea><div class="row" style="margin-top:10px"><button class="btn primary sm" id="docsalvar">Salvar</button><button class="btn sm" id="doccanc">Cancelar</button></div></div>
      <div class="muted small" style="margin-top:14px">Gerado por IA local (${esc(j.ctx_modelo || modelo)}): confira o resultado contra a transcrição antes de usar.</div></div>` : ''}
    ${(anon.tabela || []).length ? `<details class="card"><summary><b>Tabela de correspondência da anonimização</b> <span class="muted small">(guarde só localmente)</span></summary>
      <table class="table"><thead><tr><th>Original</th><th>Código</th></tr></thead><tbody>${anon.tabela.map(r => `<tr><td>${esc(r.termo)}</td><td>${esc(r.codigo)}</td></tr>`).join('')}</tbody></table></details>` : ''}`;
  const termos = () => $('#termos').value.split('\n').map(s => s.trim()).filter(Boolean);
  const anonOn = () => ent || $('#anon').checked;
  const mostra = () => $('#termosw').classList.toggle('hidden', !anonOn());
  $('#anon').onchange = mostra; mostra();
  $('#gerar').onclick = async () => {
    try { await api(`/api/jobs/${j.id}/contexto`, { json: { anonimo: anonOn(), termos: termos() } }); toast('Geração iniciada (usa a GPU; aguarde a fila).'); renderJob(j.id); } catch (x) { falha(x); }
  };
  $('#ctxcancel').onclick = () => api(`/api/jobs/${j.id}/cancelar`, { json: { tipo: 'c' } }).catch(falha);
  $('#copiarprompt').onclick = async () => {
    try { const r = await api(`/api/jobs/${j.id}/prompt?anonimo=${anonOn()}&termos=${encodeURIComponent(termos().join('|'))}`); await copiar(r.prompt); toast('Prompt copiado. Cole no Claude.'); } catch (x) { falha(x); }
  };
  $('#editar')?.addEventListener('click', () => { $('#docview').classList.add('hidden'); $('#docedit').classList.remove('hidden'); });
  $('#doccanc')?.addEventListener('click', () => { $('#docview').classList.remove('hidden'); $('#docedit').classList.add('hidden'); });
  $('#docsalvar')?.addEventListener('click', async () => { try { await api(`/api/jobs/${j.id}/contexto`, { method: 'PUT', json: { contexto: $('#doctxt').value } }); toast('Documento salvo.'); renderJob(j.id); } catch (x) { falha(x); } });
  $('#copdoc')?.addEventListener('click', async () => { await copiar(j.contexto); toast('Documento copiado.'); });
  if (gerando) { const t = setInterval(() => { if (S.rota !== 'job' || !$('#ctxbar')) return clearInterval(t); const a = S.ativos.find(x => x.id === j.id && x.tipo === 'c'); if (a) { $('#ctxbar').style.width = a.progresso + '%'; $('#ctxpct').textContent = Math.floor(a.progresso) + '%'; $('#ctxetapa').textContent = a.etapa; } }, 1000); }
}

// ---- aba: exportar
function abaExportar(j) {
  const cofre = S.estado.config.obsidian_cofre;
  const card = (ico, t, d, acoes) => `<div class="exp"><div class="ico">${ico}</div><b>${t}</b><p>${d}</p><div class="row">${acoes}</div></div>`;
  const dl = (f, rotulo, desab) => `<a class="btn sm ${desab ? 'disabled' : ''}" ${desab ? 'aria-disabled="true" style="opacity:.5;pointer-events:none"' : ''} href="/api/jobs/${j.id}/exportar/${f}">${I.down} ${rotulo}</a>`;
  $('#aba').innerHTML = `<div class="cards3">
    ${card(I.doc, 'Transcrição', 'Texto com tempos e nomes dos falantes.', dl('md', 'Markdown') + dl('docx', 'Word'))}
    ${card(I.spark, S.estado.perfis[j.perfil].documento, j.contexto ? 'Documento contextualizado gerado pelo LLM local.' : 'Gere primeiro na aba do documento.', dl('md-ata', 'Markdown', !j.contexto) + dl('docx-ata', 'Word', !j.contexto))}
    ${card(I.book, 'Obsidian', cofre ? `Salva uma nota única (documento + transcrição) em <span class="kbd">${esc(cofre)}</span>.` : 'Escolha o cofre em Configurações para habilitar.', `<button class="btn sm" id="obs" ${cofre ? '' : 'disabled'}>Enviar ao cofre</button>`)}
    ${card(I.copy, 'Copiar texto', 'Copia a transcrição completa para a área de transferência.', '<button class="btn sm" id="coptxt">Copiar</button>')}
    </div><p class="muted small" style="margin-top:16px">O arquivo <span class="kbd">${esc(j.md || '')}</span> é atualizado a cada edição e fica na pasta <span class="kbd">saida\\${esc(j.perfil)}</span>.</p>`;
  $('#obs').onclick = async () => { try { const r = await api(`/api/jobs/${j.id}/obsidian`, { method: 'POST' }); toast('Nota salva no Obsidian.'); void r; } catch (x) { falha(x); } };
  $('#coptxt').onclick = async () => { const r = await api(`/api/jobs/${j.id}/exportar/md`); await copiar(await r.text()); toast('Transcrição copiada.'); };
}

// ------------------------------------------------------------------ configurações
async function renderConfig() {
  S.estado = await api('/api/estado');
  const e = S.estado, c = e.config, oll = e.ollama;
  view.innerHTML = `<div class="page-head"><div><h1>Configurações</h1><p>Tudo é salvo localmente.</p></div></div>
  <div class="card"><div class="card-head"><div><h2>Pastas monitoradas</h2><div class="muted small">Arquivos soltos nestas pastas viram trabalhos automaticamente; a subpasta define o perfil.</div></div>
    <label class="row small" style="gap:8px"><input type="checkbox" id="mon" ${c.monitor_ativo ? 'checked' : ''}> Detecção automática ligada</label></div>
    <div class="row">${ORDEM.map(k => `<button class="btn sm" data-pasta="entrada/${k}">${I.folder} entrada\\${k}</button>`).join('')}<button class="btn sm" data-pasta="saida">${I.folder} saida</button><button class="btn sm" data-pasta="processados">${I.folder} processados</button></div></div>
  <div class="card"><div class="card-head"><div><h2>Modelo de linguagem local (Ollama)</h2><div class="muted small">Usado para gerar atas e notas. Roda na sua GPU e libera a memória ao terminar.</div></div>
    <span class="pill ${oll.ativo ? 'ok' : 'warn'}"><span class="dot"></span>${oll.ativo ? 'Em execução' : 'Parado'}</span></div>
    <div class="row"><select id="ollm" style="max-width:340px">${[...new Set([c.ollama_modelo, ...oll.modelos])].map(m => `<option ${m === c.ollama_modelo ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select>
    <span class="muted small">Para instalar outro: <span class="kbd">ollama pull nome-do-modelo</span></span></div></div>
  <div class="card"><div class="card-head"><div><h2>Obsidian</h2><div class="muted small">Pasta do cofre para exportar notas.</div></div></div>
    <div class="row"><select id="cofsel" style="max-width:420px"><option value="">Escolher cofre detectado…</option>${e.cofres_obsidian.map(v => `<option ${v === c.obsidian_cofre ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></div>
    <div class="row" style="margin-top:10px"><input type="text" id="cof" style="max-width:520px" placeholder="Ou digite o caminho do cofre" value="${esc(c.obsidian_cofre)}"><input type="text" id="sub" style="max-width:200px" placeholder="Subpasta" value="${esc(c.obsidian_subpasta)}"><button class="btn primary sm" id="salvarobs">Salvar</button></div></div>
  <div class="card"><div class="card-head"><div><h2>Prompts por perfil</h2><div class="muted small">Instruções enviadas ao LLM. Use <span class="kbd">{{participantes}}</span> e <span class="kbd">{{transcricao}}</span>.</div></div>
    <select id="pperfil" style="width:auto">${ORDEM.map(k => `<option value="${k}">${esc(e.perfis[k].nome)}</option>`).join('')}</select></div>
    <textarea id="ptxt" rows="14"></textarea><div class="row" style="margin-top:10px"><button class="btn primary sm" id="psalvar">Salvar prompt</button></div></div>
  <div class="card"><h2>Sobre</h2><p class="muted" style="margin:8px 0 0">Transcrição de áudio do Plaud Note Pro · por Vladimir Almeida<br>Transcrição: <b>${esc(e.modelo_whisper)}</b> · Falantes: pyannote · GPU: ${esc(e.gpu_nome)}<br>Nenhum áudio ou texto sai deste computador.</p></div>`;
  $$('[data-pasta]').forEach(b => b.onclick = () => api('/api/abrir-pasta', { json: { qual: b.dataset.pasta } }).catch(falha));
  $('#mon').onchange = ev => api('/api/config', { method: 'PUT', json: { monitor_ativo: ev.target.checked } }).then(r => { S.estado = r; toast(ev.target.checked ? 'Detecção ligada.' : 'Detecção desligada.'); }).catch(falha);
  $('#ollm').onchange = ev => api('/api/config', { method: 'PUT', json: { ollama_modelo: ev.target.value } }).then(r => { S.estado = r; toast('Modelo salvo.'); }).catch(falha);
  $('#cofsel').onchange = ev => { if (ev.target.value) $('#cof').value = ev.target.value; };
  $('#salvarobs').onclick = () => api('/api/config', { method: 'PUT', json: { obsidian_cofre: $('#cof').value.trim(), obsidian_subpasta: $('#sub').value.trim() || 'Transcrições' } }).then(r => { S.estado = r; toast('Obsidian configurado.'); }).catch(falha);
  const carregarPrompt = async () => { $('#ptxt').value = (await api(`/api/prompts/${$('#pperfil').value}`)).texto; };
  $('#pperfil').onchange = carregarPrompt; carregarPrompt().catch(falha);
  $('#psalvar').onclick = () => api(`/api/prompts/${$('#pperfil').value}`, { method: 'PUT', json: { texto: $('#ptxt').value } }).then(() => toast('Prompt salvo.')).catch(falha);
}

// ---------------------------------------------------------------- cancelamentos
document.addEventListener('click', ev => {
  const b = ev.target.closest('[data-cancelar]');
  if (b) api(`/api/jobs/${b.dataset.cancelar}/cancelar`, { json: { tipo: b.dataset.tipo } }).then(() => toast('Cancelando…')).catch(falha);
});
window.addEventListener('beforeunload', ev => { if (S.dirty) { ev.preventDefault(); ev.returnValue = ''; } });

// ------------------------------------------------------------------------- início
(async function iniciar() {
  try {
    S.estado = await api('/api/estado');
    S.gpu = await api('/api/gpu/historico');
    S.prog = await api('/api/progresso');
  } catch (e) { view.innerHTML = `<div class="callout err">Não foi possível conectar ao servidor local: ${esc(e.message)}</div>`; return; }
  conectar(); rota();
})();
