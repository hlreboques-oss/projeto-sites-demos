#!/usr/bin/env python3
import csv, json, os, re, sys, time, urllib.request, urllib.error, datetime, unicodedata, pathlib, subprocess
ROOT=pathlib.Path('/root/projeto-sites-demos')
CRM=ROOT/'projeto_sites_crm.csv'
ACT=ROOT/'projeto_sites_atividades.csv'
ENV=pathlib.Path('/root/evolution-whatsapp-agent/.env')
BASE='http://127.0.0.1:8085'
INST='projeto-sites'
STAGE2A_TEMPLATE="""Obrigada 😊 Meu nome é Mayara.
Tenho ajudado empresas do ramo de {area} a ter uma visibilidade melhor na internet através de sites construídos de forma personalizada.

Minha dúvida é saber se você autoriza eu criar um site para você, só para você ver como que fica. Sem compromisso nenhum, e eu entrego em poucos minutos."""
STAGE2_TEMPLATE="""Que bom! Aqui está uma sugestão de página para vocês, usando as informações que encontrei publicamente:
👉 {demo_url}

Não precisa comprar nada, viu? É só uma ideia que preparei para vocês.
Se essa página fosse sua hoje, qual seria a primeira coisa que você mudaria nela?"""
STAGE3="Ah, e só para ser transparente: eu sou uma inteligência artificial. Faço parte de uma operação que ajuda empresas a vender mais, e posso realizar tarefas como essa — pesquisar, criar conteúdo e site, e conversar com você — de ponta a ponta. Faz sentido eu te explicar por aqui ou prefere uma call rápida de 10 minutos com o Carlos?"
ALREADY_SITE="Perfeito, obrigado por me avisar. Nesse caso não é sobre ‘ter ou não ter site’.\nAlém de site, eu também identifico pontos de atendimento, captação, organização do WhatsApp e conversão. Se quiser, eu posso te mostrar rapidamente o que percebi no posicionamento online de vocês."

NICHE_KEYWORDS=[
    ('odont','odontologia estética'),
    ('harmoniza','harmonização facial'),
    ('facial','estética facial'),
    ('corporal','estética corporal e facial'),
    ('depila','depilação a laser'),
    ('laser','depilação a laser'),
    ('sobrancel','sobrancelhas e cílios'),
    ('cilios','sobrancelhas e cílios'),
    ('micropigmenta','micropigmentação'),
    ('fisio','fisioterapia dermatofuncional'),
    ('massage','massagem e drenagem'),
    ('massoter','massagem relaxante'),
    ('drenagem','drenagem linfática'),
    ('dermato','dermatologia estética'),
    ('estetica automotiva','estética automotiva'),
    ('mecanic','serviços automotivos'),
    ('auto','serviços automotivos'),
    ('cabelei','cabeleireiro e beleza'),
    ('salao','salão de beleza'),
    ('beleza','estética e beleza'),
    ('spa','spa e bem-estar'),
]
def area_atuacao(lead):
    blob=norm(' '.join([lead.get('nome') or '', lead.get('vulnerabilidade') or '', lead.get('site_status') or '', lead.get('notes') or '']))
    for kw,label in NICHE_KEYWORDS:
        if kw in blob: return label
    return 'estética e beleza'
ACT_FIELDS=['ts','lead_id','nome','telefone','tipo','etapa_de','etapa_para','mensagem_id','resumo','proxima_acao']

def now(): return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','+00:00')
def parse_time(s):
    if not s: return 0
    try: return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
    except Exception: return 0

def digits(s): return re.sub(r'\D+','',s or '')
def norm(s):
    s=(s or '').lower()
    s=''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    return re.sub(r'\s+',' ',s).strip()
def get_key():
    m=re.search(r'^AUTHENTICATION_API_KEY=(.*)$', ENV.read_text(), re.M)
    if not m: raise RuntimeError('AUTHENTICATION_API_KEY ausente')
    return m.group(1).strip().strip('"\'')
KEY=get_key()
def req(method, path, payload=None, timeout=60):
    data=None
    headers={'apikey':KEY, 'Content-Type':'application/json'}
    if payload is not None: data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    r=urllib.request.Request(BASE+path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw=resp.read().decode('utf-8','replace')
        return json.loads(raw) if raw else {}

def extract_text(m):
    msg=m.get('message') or {}
    if not isinstance(msg,dict): return ''
    return msg.get('conversation') or (msg.get('extendedTextMessage') or {}).get('text') or (msg.get('imageMessage') or {}).get('caption') or (msg.get('videoMessage') or {}).get('caption') or ''
def msg_ts(m):
    v=m.get('messageTimestamp') or 0
    try: v=int(v)
    except Exception: return 0
    if v>10_000_000_000: v//=1000
    return v

def load_csv(path):
    if not path.exists(): return [], []
    with path.open(newline='',encoding='utf-8') as f:
        rd=csv.DictReader(f); return rd.fieldnames or [], list(rd)
def save_csv(path, fields, rows):
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    tmp.replace(path)
def append_acts(rows):
    exists=ACT.exists()
    with ACT.open('a',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ACT_FIELDS)
        if not exists: w.writeheader()
        for r in rows: w.writerow({k:r.get(k,'') for k in ACT_FIELDS})

def read_activities():
    fields, rows=load_csv(ACT)
    return rows

def infer_stage(lead, acts):
    raw=(lead.get('script_stage') or '').strip()
    if raw in ('2a','2b'): return raw
    if raw:
        try: return int(raw)
        except Exception: pass
    last=''
    for a in acts:
        if a.get('lead_id')==lead.get('lead_id') and a.get('tipo','').startswith('outbound'):
            last=a.get('tipo','')
    if last=='outbound_ia_reveal': return 3
    if last=='outbound_demo': return 2
    if last=='outbound_curiosidade': return 3
    return 1

def classify_stage1(text):
    t=norm(text)
    bot_terms=['assistente virtual','chatbot','sou uma ia','sou uma inteligencia artificial','atendimento automatizado por ia','bot de atendimento','robô','robo']
    if any(x in t for x in bot_terms): return 'bot_terceiro'
    auto_terms=['atendimento automatico','mensagem automatica','horario de atendimento','fora do horario','em breve retornaremos','assim que possivel','favor aguardar','aguarde','estamos ocupados','no momento nao estamos disponiveis','no momento nao estamos em funcionamento','ja vamos te atender','ja ja te atendo','deixe seu nome','deixe sua mensagem','deixe abaixo seu nome','deixe abaixo seu nome e assunto','menu','digite','opcao','opcoes','retornaremos','bem-vindo','bem vindo','bem vinda','bem-vinda','seja bem vinda','seja bem vindo','seja muito bem vinda','seja muito bem vindo','seja muito bem-vinda','seja muito bem-vindo','agradece seu contato','como podemos ajudar','nosso espaco foi criado','nosso espaço foi criado','sera um prazer cuidar','será um prazer cuidar','para melhor atendimento','este numero sera inativado','este numero será inativado','entre em contato com meu novo numero','entre em contato com meu novo número']
    if any(x in t for x in auto_terms): return 'auto_negocio'
    stop_terms=['nao existe mais','empresa fechou','fechado','paralisada','paralisado','numero errado','nao conheco','nao e aqui','não é aqui']
    if any(norm(x) in t for x in stop_terms): return 'stop'
    return 'humano'

def classify_response(text):
    t=norm(text)
    neg_patterns=[
        'pare','parar','remova','nao quero','sem interesse','nao tenho interesse','nao temos interesse',
        'nao ha interesse','nao possuo interesse','nao temos necessidade','nao preciso','nao precisamos',
        'nao faz sentido','obrigado nao','dispenso','esta bom obrigado','está bom obrigado',
        'o que ja tenho esta bom','o que já tenho está bom'
    ]
    if any(x in t for x in neg_patterns): return 'negativo'
    if any(x in t for x in ['ja tenho site','temos site','tenho site','site ja','ja possuo site']): return 'ja_tem_site'
    if any(x in t for x in ['valor','preco','preço','quanto','orçamento','orcamento','forma de pagamento']): return 'preco_interesse'
    positive_patterns=['sim','quero','manda','envia','pode mandar','faz sentido','interessante','como assim','me mostra','mostrar','gostei','legal','claro','ok','pode ser','vamos','call','ligacao','explica','explicar']
    if any(x in t for x in positive_patterns) or re.search(r'(^|\b)(tenho|temos|possuo|possuimos) interesse(\b|$)', t): return 'interesse'
    if '?' in text: return 'interesse'
    return 'neutro'

def fetch_recent(pages=12):
    all=[]
    for p in range(1,pages+1):
        data=req('POST',f'/chat/findMessages/{INST}',{'page':p,'limit':100,'perPage':100},timeout=60)
        rec=(data.get('messages') or {}).get('records') or []
        if not rec: break
        all.extend(rec)
    by={}
    for m in all:
        mid=(m.get('key') or {}).get('id') or m.get('id')
        if mid: by[mid]=m
    return sorted(by.values(), key=msg_ts)

def send(number_or_jid, text):
    payload={'number': number_or_jid, 'text': text}
    return req('POST',f'/message/sendText/{INST}',payload,timeout=45)

def verify_outbound(mid, remote, fragment):
    time.sleep(1.5)
    rec=fetch_recent(4)
    f=norm(fragment)[:80]
    for m in rec:
        key=m.get('key') or {}
        if not key.get('fromMe'): continue
        if remote and key.get('remoteJid')!=remote: continue
        txt=extract_text(m)
        if (mid and (key.get('id')==mid or m.get('id')==mid)) or (f and f in norm(txt)):
            return True
    return False

def main():
    state=req('GET',f'/instance/connectionState/{INST}',None,timeout=20)
    if (state.get('instance') or {}).get('state')!='open':
        print(json.dumps({'blocked':'evolution_not_open','state':state},ensure_ascii=False)); return 2
    fields, leads=load_csv(CRM)
    if 'script_stage' not in fields:
        insert_at=fields.index('abordagem_status')+1 if 'abordagem_status' in fields else len(fields)
        fields=fields[:insert_at]+['script_stage']+fields[insert_at:]
        for r in leads: r['script_stage']=''
    acts=read_activities()
    processed={a.get('mensagem_id') for a in acts if a.get('mensagem_id')}
    phone_to_lead={digits(r.get('wa_link') or r.get('telefone'))+'@s.whatsapp.net':r for r in leads if digits(r.get('wa_link') or r.get('telefone'))}
    messages=fetch_recent()
    actions=[]; newacts=[]; changed=False
    for lead in leads:
        if lead.get('etapa') not in ('enviado','qualificando','negociando','follow_up'): continue
        remote=digits(lead.get('wa_link') or lead.get('telefone'))+'@s.whatsapp.net'
        stage=infer_stage(lead, acts+newacts)
        if not lead.get('script_stage') or lead.get('script_stage')!=str(stage):
            lead['script_stage']=str(stage); changed=True
        last_out=parse_time(lead.get('last_outbound_at'))
        relevant=[]
        for m in messages:
            key=m.get('key') or {}; mid=key.get('id') or m.get('id') or ''
            if key.get('fromMe') or mid in processed or key.get('remoteJid','').endswith('@g.us'): continue
            rem=key.get('remoteJid') or ''
            alt=key.get('remoteJidAlt') or ''
            if rem!=remote and alt!=remote: continue
            # Evolution/CRM timestamps can differ by seconds on immediate auto-replies: the CRM
            # last_outbound_at is written after the readback check, so it lands 20-40s AFTER the
            # real WhatsApp send time and a greeting that arrived in between would be dropped.
            # Keep a 240s grace window so business greetings right after the opener are logged.
            if msg_ts(m) + 240 < last_out: continue
            txt=extract_text(m).strip()
            if txt: relevant.append(m)
        if not relevant: continue
        # process newest unprocessed inbound for the lead this tick, but log all inbound snippets
        for m in relevant:
            key=m.get('key') or {}; mid=key.get('id') or m.get('id') or ''; txt=extract_text(m).strip()
            newacts.append({'ts':datetime.datetime.fromtimestamp(msg_ts(m), datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','+00:00'),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'inbound','etapa_de':lead.get('etapa'),'etapa_para':lead.get('etapa'),'mensagem_id':mid,'resumo':txt[:240],'proxima_acao':'avaliar resposta'})
            processed.add(mid); changed=True
        newest=relevant[-1]; txt=extract_text(newest).strip(); mid=(newest.get('key') or {}).get('id') or newest.get('id') or ''
        old_etapa=lead.get('etapa')
        remote_actual=(newest.get('key') or {}).get('remoteJid') or remote
        if stage=='1' or stage==1:
            # If an automatic greeting is followed by a genuine human reply and later
            # another canned/autopromo message, continue from the human reply instead
            # of letting the newest automated-looking text mask the human response.
            stage1_choices=[]
            for cand in relevant:
                ctxt=extract_text(cand).strip()
                if not ctxt: continue
                ccls=classify_stage1(ctxt)
                stage1_choices.append((ccls, cand, ctxt))
            chosen=None
            for ccls,cand,ctxt in stage1_choices:
                if ccls in ('bot_terceiro','stop'):
                    chosen=(ccls,cand,ctxt); break
            if chosen is None:
                for ccls,cand,ctxt in reversed(stage1_choices):
                    if ccls=='humano':
                        chosen=(ccls,cand,ctxt); break
            if chosen is None and stage1_choices:
                chosen=stage1_choices[-1]
            if chosen:
                cls, chosen_msg, txt = chosen
                mid=(chosen_msg.get('key') or {}).get('id') or chosen_msg.get('id') or mid
                remote_actual=(chosen_msg.get('key') or {}).get('remoteJid') or remote_actual
            else:
                cls=classify_stage1(txt)
            if cls=='bot_terceiro':
                lead.update(etapa='desativado',motivo_etapa='respondido por IA/bot de terceiro',abordagem_status='resposta_recebida_desativado',last_inbound_at=now(),updated_at=now(),notes=((lead.get('notes') or '')+'\n Resposta: '+txt).strip())
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':'desativado','mensagem_id':mid,'resumo':'Respondido por IA/bot de terceiro; conversa parada.','proxima_acao':'não contatar'})
                actions.append((lead.get('nome'), 'IA/bot terceiro', old_etapa+' stage 1', 'desativado', None, 'não contatar'))
            elif cls=='auto_negocio':
                lead.update(last_inbound_at=now(),updated_at=now(),script_stage='1',motivo_etapa='resposta automática recebida; aguardando humano',abordagem_status='resposta_automatica_aguardando')
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':old_etapa,'mensagem_id':mid,'resumo':'Resposta automática do negócio; sem envio para não pular estágio.','proxima_acao':'aguardar resposta humana'})
                actions.append((lead.get('nome'), 'automática do negócio', old_etapa+' stage 1', old_etapa+' stage 1', None, 'aguardar humano'))
            elif cls=='stop':
                lead.update(etapa='desativado',motivo_etapa='contato informou empresa/contato inválido ou fechado',abordagem_status='resposta_recebida_desativado',last_inbound_at=now(),updated_at=now(),notes=((lead.get('notes') or '')+'\n Resposta: '+txt).strip())
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':'desativado','mensagem_id':mid,'resumo':'Contato indicou empresa/contato inválido ou fechado; não contatar.','proxima_acao':'não contatar'})
                actions.append((lead.get('nome'), 'encerramento/inválido', old_etapa+' stage 1', 'desativado', None, 'não contatar'))
            else:
                area=area_atuacao(lead)
                msg=STAGE2A_TEMPLATE.format(area=area)
                resp=send(remote_actual, msg); outid=(resp.get('key') or {}).get('id') or resp.get('messageId') or ''
                ok=verify_outbound(outid, remote_actual, 'posso criar um site')
                if not ok: raise RuntimeError('readback falhou para pedido de permissao '+lead.get('nome',''))
                lead.update(etapa='qualificando',motivo_etapa='respondeu ao opener (humano genuino); pedido de permissão para site enviado',abordagem_status='permissao_solicitada',last_inbound_at=now(),last_outbound_at=now(),updated_at=now(),last_message_id=outid,script_stage='2a',outbound_count=str(int(lead.get('outbound_count') or '0')+1))
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'outbound_permissao','etapa_de':old_etapa,'etapa_para':'qualificando','mensagem_id':outid,'resumo':'Resposta humana genuína classificada; enviado pedido de permissão para criar site (Estágio 2a, sem demo/link ainda); envio verificado por readback.','proxima_acao':'aguardar autorização explícita antes de construir qualquer demo'})
                actions.append((lead.get('nome'), 'humana genuína', old_etapa+' stage 1', 'qualificando stage 2a', msg, 'aguardar autorização'))
        elif stage=='2a':
            cls=classify_response(txt)
            if cls in ('interesse',) or re.search(r'\b(pode|manda|quero ver|topo|claro|pode sim|pode mandar)\b', norm(txt)):
                lead.update(needs_human='true', script_stage='2b', updated_at=now(), last_inbound_at=now(),
                            motivo_etapa='autorizou a criação do site; aguardando build manual/agente antes de qualquer envio de link',
                            abordagem_status='autorizado_aguardando_build',
                            notes=((lead.get('notes') or '')+'\nAutorização recebida: '+txt).strip())
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':old_etapa,'mensagem_id':mid,'resumo':'Lead autorizou explicitamente a criação do site; nenhuma demo construída ainda, aguardando build (Estágio 2b).','proxima_acao':'construir e publicar demo, depois enviar mensagem de entrega'})
                actions.append((lead.get('nome'), 'autorizou site (2a->2b)', old_etapa+' stage 2a', old_etapa+' stage 2b', None, 'construir demo'))
            elif cls=='ja_tem_site':
                resp=send(remote_actual, ALREADY_SITE); outid=(resp.get('key') or {}).get('id') or resp.get('messageId') or ''
                ok=verify_outbound(outid, remote_actual, 'Além de site')
                if not ok: raise RuntimeError('readback falhou site existente '+lead.get('nome',''))
                lead.update(etapa='qualificando',motivo_etapa='lead informou já ter site; pivot enviado',abordagem_status='pivot_site_existente_enviado',last_inbound_at=now(),last_outbound_at=now(),updated_at=now(),last_message_id=outid,outbound_count=str(int(lead.get('outbound_count') or '0')+1))
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'outbound_pivot_site','etapa_de':old_etapa,'etapa_para':'qualificando','mensagem_id':outid,'resumo':'Lead disse que já tem site; pivot de atendimento/captação enviado; readback verificado.','proxima_acao':'monitorar interesse'})
                actions.append((lead.get('nome'), 'já tem site', old_etapa+' stage 2a', 'qualificando stage 2a', ALREADY_SITE, 'monitorar'))
            elif cls=='negativo':
                lead.update(etapa='nao_converteu',motivo_etapa='recusou autorização para criar o site',abordagem_status='negativo_sem_autorizacao',last_inbound_at=now(),updated_at=now())
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':'nao_converteu','mensagem_id':mid,'resumo':'Resposta negativa ao pedido de permissão; sem construir nada, sem insistir.','proxima_acao':'não seguir agora'})
                actions.append((lead.get('nome'), 'negativa (permissão)', old_etapa+' stage 2a', 'nao_converteu', None, 'não seguir'))
            else:
                lead.update(last_inbound_at=now(),updated_at=now(),motivo_etapa='resposta ao pedido de permissão sem sim/não claro; aguardando revisão',abordagem_status='permissao_resposta_ambigua')
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':old_etapa,'mensagem_id':mid,'resumo':'Resposta ambígua ao pedido de permissão; não construir nada ainda: '+txt[:160],'proxima_acao':'aguardar confirmação clara (sim/pode/manda) antes de construir'})
                actions.append((lead.get('nome'), 'ambígua (permissão)', old_etapa+' stage 2a', old_etapa+' stage 2a', None, 'aguardar confirmação'))
        elif stage=='2b':
            lead.update(last_inbound_at=now(),updated_at=now())
            newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':old_etapa,'mensagem_id':mid,'resumo':'Lead já autorizado, aguardando build manual/agente da demo; nova mensagem registrada sem envio automático: '+txt[:160],'proxima_acao':'concluir build e enviar demo'})
            actions.append((lead.get('nome'), 'aguardando build (2b)', old_etapa+' stage 2b', old_etapa+' stage 2b', None, 'concluir build'))
        elif stage==3:
            cls=classify_response(txt)
            if cls in ('interesse','preco_interesse'):
                msg=STAGE3
                if cls=='preco_interesse':
                    msg += "\n\nSobre valor: um site normal costuma ficar entre R$ 800 e R$ 1.500. Nesta ação, o projeto sai por R$ 350 ou 12x de R$ 35, com personalização completa do site final."
                resp=send(remote_actual, msg); outid=(resp.get('key') or {}).get('id') or resp.get('messageId') or ''
                ok=verify_outbound(outid, remote_actual, 'só para ser transparente')
                if not ok: raise RuntimeError('readback falhou IA reveal '+lead.get('nome',''))
                lead.update(etapa='negociando',motivo_etapa='engajou com demo; revelação de IA enviada',abordagem_status='ia_revelada_apos_engajamento',last_inbound_at=now(),last_outbound_at=now(),updated_at=now(),last_message_id=outid,script_stage='4',outbound_count=str(int(lead.get('outbound_count') or '0')+1))
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'outbound_ia_reveal','etapa_de':old_etapa,'etapa_para':'negociando','mensagem_id':outid,'resumo':'Engajamento real com demo; revelação de IA (Estágio 4) enviada; readback verificado.','proxima_acao':'conduzir explicação/call/preço'})
                actions.append((lead.get('nome'), cls, old_etapa+' stage 3', 'negociando stage 4', msg, 'conduzir negociação'))
            elif cls=='negativo':
                lead.update(etapa='nao_converteu',motivo_etapa='resposta negativa após demo',abordagem_status='negativo_apos_demo',last_inbound_at=now(),updated_at=now())
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':'nao_converteu','mensagem_id':mid,'resumo':'Resposta negativa após demo; sem insistir.','proxima_acao':'não seguir agora'})
                actions.append((lead.get('nome'), 'negativa após demo', old_etapa+' stage 3', 'nao_converteu', None, 'não seguir'))
            else:
                lead.update(last_inbound_at=now(),updated_at=now(),motivo_etapa='resposta após demo sem interesse claro; aguardando revisão/novo contexto',abordagem_status='resposta_pos_demo_monitorada_sem_envio')
                newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':old_etapa,'mensagem_id':mid,'resumo':'Resposta após demo sem interesse claro; sem envio automático: '+txt[:160],'proxima_acao':'aguardar contexto comercial claro'})
                actions.append((lead.get('nome'), 'pós-demo neutra', old_etapa+' stage 3', old_etapa+' stage 3', None, 'aguardar contexto'))
        else:
            lead.update(last_inbound_at=now(),updated_at=now())
            newacts.append({'ts':now(),'lead_id':lead.get('lead_id'),'nome':lead.get('nome'),'telefone':lead.get('telefone'),'tipo':'sistema','etapa_de':old_etapa,'etapa_para':old_etapa,'mensagem_id':mid,'resumo':'Resposta em estágio avançado registrada sem envio automático: '+txt[:160],'proxima_acao':'revisar negociação'})
            actions.append((lead.get('nome'), 'resposta em estágio avançado', old_etapa+f' stage {stage}', old_etapa+f' stage {stage}', None, 'revisar negociação'))
        changed=True
    if changed:
        save_csv(CRM, fields, leads)
        if newacts: append_acts(newacts)
        subprocess.check_call(['python','/root/.hermes/scripts/projeto_sites_export_xlsx.py'], cwd=str(ROOT))
    print(json.dumps({'actions':actions,'changed':changed,'new_activities':len(newacts)},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':
    sys.exit(main())
