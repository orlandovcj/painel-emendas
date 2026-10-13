#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para Atualização da Base de Pagamentos a Pessoas Jurídicas (pagamentos_pj.csv)
====================================================================================
Este script consome as APIs públicas do Transferegov para:
1. Verificar e sincronizar novas contas bancárias de emendas parlamentares em SC
   (preenchendo dados de contas que não constavam anteriormente na base local).
2. Consultar os extratos bancários das contas de Transferências Especiais (Emendas PIX)
   dos municípios de SC.
3. Compilar todos os débitos destinados a fornecedores e prestadores de serviços (PJ).

Entrada:
    dados/emendas_sc.csv (base de emendas parlamentares de SC)

Saída:
    dados/pagamentos_pj.csv (base consolidada de pagamentos a PJs)
    dados/emendas_sc.csv (atualizado caso novas contas bancárias sejam descobertas)

Uso:
    python atualizar_pagamentos_pj.py
    python atualizar_pagamentos_pj.py --workers 8
    python atualizar_pagamentos_pj.py --limite 10       # Teste rápido com 10 contas
    python atualizar_pagamentos_pj.py --no-sync-contas # Desativa sincronização prévia de contas
"""

import os
import sys
import json
import time
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("AtualizarPagamentosPJ")

API_LANCAMENTOS_URL = "https://api-publica.transferegov.gestao.gov.br/especiais/gestao-financeira-lancamentos-especiais"
API_PLANOS_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PainelEmendasSC/1.0"


def create_session(retries=3, backoff_factor=1.0):
    """Cria uma sessão HTTP com política de retry e pooling de conexões."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json"
    })
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def clean_digits(val):
    """Extrai somente os dígitos numéricos de um campo."""
    if pd.isna(val) or val is None:
        return ""
    val_str = str(val).split(".")[0].strip()
    return "".join([c for c in val_str if c.isdigit()])


def standardize_cnpj(val):
    """Padroniza e formata o CNPJ com 14 dígitos e zero à esquerda."""
    digits = clean_digits(val)
    if not digits:
        return ""
    if len(digits) <= 14:
        return digits.zfill(14)
    return digits[:14]


def is_pj_transaction(tx):
    """Verifica se a transação do extrato representa débito destinado a Pessoa Jurídica fornecedora de obras/serviços."""
    # Apenas operações de débito (saída de recursos)
    if tx.get("tipo_operacao_gestao_financeira") != "D":
        return False

    doc = tx.get("doc_favorecido_gestao_financeira")
    doc_digits = clean_digits(doc)
    tipo = tx.get("tipo_favorecido_gestao_financeira")

    # tipo 2 indica Pessoa Jurídica na API Transferegov
    is_pj = (str(tipo) in ("2", "2.0")) or (len(doc_digits) > 11)

    fav = tx.get("nome_favorecido_gestao_financeira")
    has_valid_name = (
        pd.notna(fav) and
        isinstance(fav, str) and
        fav.strip() != "" and
        fav.strip().lower() not in ("nan", "none", "***")
    )
    if not (is_pj and has_valid_name):
        return False

    fav_upper = fav.upper().strip()
    doc_14 = doc_digits.zfill(14)
    desc_upper = str(tx.get("descricao_gestao_financeira") or "").upper().strip()

    # 1. Desconsiderar Bancos, Aplicações Financeiras e Tarifas
    # Banco do Brasil (raiz 00000000), Caixa Econômica (raiz 00360305) e outras instituições financeiras
    if doc_14.startswith("00000000") or doc_14.startswith("00360305"):
        return False
    if any(b in fav_upper for b in [
        "BANCO DO BRASIL", "CAIXA ECONOMICA", "BANRISUL", "BRADESCO", "ITAU", "SANTANDER",
        "DTVM", "DISTRIBUIDORA DE TITULOS", "CORRETORA DE VALORES"
    ]):
        return False
    if any(op in desc_upper for op in [
        "BB-APLIC", "APLIC", "INVESTIMENTO", "FUNDO", "RESGATE", "APL.AUT",
        "TARIFA", "DOC/TED INTERNET", "TAR COBRANCA", "MANUT CONTA", "PACOTE SERVICOS"
    ]):
        return False

    # 2. Desconsiderar Transferências Internas para a própria Prefeitura / Ente Público (mesma titularidade)
    cnpj_ente = clean_digits(tx.get("cnpj_ente_solicitante_gestao_financeira") or "").zfill(14)
    if doc_14 and cnpj_ente and doc_14 == cnpj_ente:
        return False
    if any(term in desc_upper for term in ["MESM T", "MESMA TITULARIDADE", "MESMO TITULAR"]):
        return False
    if any(m in fav_upper for m in ["MUNICIPIO DE", "PREFEITURA", "ESTADO DE SANTA CATARINA", "SECRETARIA DE ESTADO"]):
        return False

    return True


def sync_bank_accounts_from_transferegov(session, df_emendas_full, filepath, ano_min=2020):
    """
    Consulta os planos de ação mais recentes de SC na API do Transferegov
    e atualiza emendas que estavam sem agência/conta na base local.
    """
    logger.info("🔍 Verificando novas contas correntes cadastradas na API do Transferegov (SC)...")
    offset = 0
    limit = 1000
    all_planos = []

    while True:
        url = (
            f"{API_PLANOS_URL}?uf_beneficiario_plano_acao=eq.SC"
            f"&ano_emenda_parlamentar_plano_acao=gte.{ano_min}"
            f"&limit={limit}&offset={offset}"
        )
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Resposta status {resp.status_code} ao buscar planos de ação.")
                break
            data = resp.json()
            if not data:
                break
            all_planos.extend(data)
            offset += limit
        except Exception as e:
            logger.error(f"Erro ao buscar planos de ação na API: {e}")
            break

    if not all_planos:
        logger.info("Nenhum dado retornado na busca de planos de ação. Mantendo base local atual.")
        return df_emendas_full

    logger.info(f"Total de planos consultados na API Transferegov: {len(all_planos)}")

    # Mapear planos por (cnpj_muni_14, codigo_emenda_12)
    api_map = {}
    for p in all_planos:
        cnpj = clean_digits(p.get("cnpj_beneficiario_plano_acao", "")).zfill(14)
        emenda = str(p.get("numero_emenda_parlamentar_plano_acao", ""))[:12]
        if cnpj and emenda:
            api_map[(cnpj, emenda)] = p

    df_updated = df_emendas_full.copy()

    # 1. Identificar se existem emendas totalmente novas na API que não constam na base local
    local_keys = set()
    for _, row in df_updated.iterrows():
        cnpj_loc = clean_digits(row.get("cnpj_municipio", "")).zfill(14)
        em_loc = str(row.get("codigo_emenda", ""))[:12]
        if cnpj_loc and em_loc:
            local_keys.add((cnpj_loc, em_loc))

    new_emendas_rows = []
    for (cnpj, emenda), p in api_map.items():
        if (cnpj, emenda) not in local_keys:
            # Montar nova linha com a mesma estrutura de colunas de emendas_sc.csv
            parlamentar_nome = str(p.get("nome_parlamentar_emenda_plano_acao") or "").strip()
            codigo_emenda_fmt = f"{emenda}-{parlamentar_nome}" if parlamentar_nome else emenda

            v_inv = float(p.get("valor_investimento_plano_acao") or 0.0)
            v_cust = float(p.get("valor_custeio_plano_acao") or 0.0)
            valor_total = v_inv + v_cust

            cta_api = clean_digits(p.get("numero_conta_plano_acao", ""))
            dv_cta = str(p.get("dv_conta_plano_acao") or "").strip()
            cta_fmt = f"{cta_api}-{dv_cta}" if (cta_api and dv_cta) else cta_api

            ag_api = clean_digits(p.get("numero_agencia_plano_acao", ""))
            dv_ag = str(p.get("dv_agencia_plano_acao") or "").strip()
            ag_fmt = f"{ag_api}-{dv_ag}" if (ag_api and dv_ag) else ag_api

            new_emendas_rows.append({
                "codigo_plano_acao": str(p.get("codigo_plano_acao") or "").strip(),
                "codigo_emenda": codigo_emenda_fmt,
                "cnpj_municipio": cnpj,
                "nome_municipio": str(p.get("nome_beneficiario_plano_acao") or "").strip(),
                "codigo_parlamentar": str(p.get("codigo_parlamentar_emenda_plano_acao") or "").strip(),
                "nome_parlamentar": parlamentar_nome,
                "valor_emenda": str(valor_total) if valor_total > 0 else "",
                "objeto_emenda": "",
                "numeros_ordens_bancarias_pagas": "",
                "banco": str(p.get("nome_banco_plano_acao") or "").strip(),
                "codigo_banco": clean_digits(p.get("codigo_banco_plano_acao", "")),
                "agencia": ag_fmt,
                "agencia_sem_dv": ag_api,
                "conta_corrente": cta_fmt,
                "conta_corrente_sem_dv": cta_api
            })

    if new_emendas_rows:
        df_new = pd.DataFrame(new_emendas_rows)
        df_updated = pd.concat([df_updated, df_new], ignore_index=True)
        logger.info(f"✨ Encontradas {len(new_emendas_rows)} NOVAS emendas parlamentares na API! Adicionadas à base.")

    # 2. Identificar e atualizar emendas existentes com novas contas correntes
    updated_count = 0
    for idx, row in df_updated.iterrows():
        cta_atual = clean_digits(row.get("conta_corrente_sem_dv", ""))
        cnpj_local = clean_digits(row.get("cnpj_municipio", "")).zfill(14)
        emenda_local = str(row.get("codigo_emenda", ""))[:12]

        p = api_map.get((cnpj_local, emenda_local))
        if not p:
            continue

        cta_api = clean_digits(p.get("numero_conta_plano_acao", ""))
        ag_api = clean_digits(p.get("numero_agencia_plano_acao", ""))
        banco_cod_api = clean_digits(p.get("codigo_banco_plano_acao", ""))
        banco_nome_api = str(p.get("nome_banco_plano_acao", "")).strip()

        # Se não tinha conta localmente e a API agora tem:
        if not cta_atual and cta_api:
            updated_count += 1
            df_updated.at[idx, "conta_corrente_sem_dv"] = cta_api
            dv_cta = str(p.get("dv_conta_plano_acao") or "").strip()
            df_updated.at[idx, "conta_corrente"] = f"{cta_api}-{dv_cta}" if dv_cta else cta_api

            if ag_api:
                df_updated.at[idx, "agencia_sem_dv"] = ag_api
                dv_ag = str(p.get("dv_agencia_plano_acao") or "").strip()
                df_updated.at[idx, "agencia"] = f"{ag_api}-{dv_ag}" if dv_ag else ag_api

            if banco_cod_api:
                df_updated.at[idx, "codigo_banco"] = banco_cod_api
            if banco_nome_api:
                df_updated.at[idx, "banco"] = banco_nome_api

            cod_plano_api = str(p.get("codigo_plano_acao") or "").strip()
            if cod_plano_api:
                df_updated.at[idx, "codigo_plano_acao"] = cod_plano_api

    if updated_count > 0:
        logger.info(f"✨ Encontradas {updated_count} novas contas correntes cadastradas na API!")

    # 3. Salvar alterações na base de emendas se houver novidades
    if len(new_emendas_rows) > 0 or updated_count > 0:
        backup_emendas = f"{filepath}.bak"
        try:
            if os.path.exists(backup_emendas):
                os.remove(backup_emendas)
            os.rename(filepath, backup_emendas)
            df_updated.to_csv(filepath, sep=";", index=False, encoding="utf-8")
            logger.info(f"Base de emendas salva e atualizada com sucesso em: {filepath}")
        except Exception as e:
            logger.warning(f"Erro ao salvar atualização de {filepath}: {e}")
    else:
        logger.info("Nenhuma nova emenda ou conta adicional identificada (base já 100% sincronizada).")

    return df_updated


def fetch_account_transactions(session, cnpj_muni, banco, agencia, conta, timeout=15):
    """
    Busca todas as páginas de movimentações financeiras para uma conta bancária.
    Retorna uma lista com todas as transações da conta.
    """
    all_transactions = []
    page = 1
    total_pages = 1

    cnpj_clean = clean_digits(cnpj_muni).zfill(14)
    banco_clean = clean_digits(banco)
    agencia_clean = clean_digits(agencia)
    conta_clean = clean_digits(conta)

    if not (cnpj_clean and banco_clean and agencia_clean and conta_clean):
        return []

    while page <= total_pages:
        params = {
            "cnpj_ente_solicitante_gestao_financeira": cnpj_clean,
            "codigo_banco_gestao_financeira": banco_clean,
            "codigo_agencia_gestao_financeira": agencia_clean,
            "codigo_conta_gestao_financeira": conta_clean,
            "pagina": page,
            "tamanho_da_pagina": 200
        }
        try:
            resp = session.get(API_LANCAMENTOS_URL, params=params, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                if items:
                    all_transactions.extend(items)
                total_pages = data.get("total_pages", 1)
                page += 1
            elif resp.status_code == 404:
                # Conta sem registros
                break
            else:
                logger.warning(
                    f"Status {resp.status_code} na conta {banco_clean}/{agencia_clean}/{conta_clean} (pág {page})"
                )
                break
        except Exception as e:
            logger.error(
                f"Erro na requisição da conta {banco_clean}/{agencia_clean}/{conta_clean}: {e}"
            )
            break

    return all_transactions


def load_emendas_data(filepath, session, sync_contas=True, ano_min=2020):
    """Carrega, sincroniza e filtra a base de emendas parlamentares de SC a partir de ano_min."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

    logger.info(f"Lendo base de emendas: {filepath}")
    df_full = pd.read_csv(filepath, sep=";", dtype=str)

    # Etapa de Sincronização prévia de novas contas com a API do Transferegov
    if sync_contas:
        df_full = sync_bank_accounts_from_transferegov(session, df_full, filepath, ano_min=ano_min)

    # Extrair ano da emenda a partir dos primeiros 4 dígitos do código
    df = df_full.copy()
    df["ano"] = df["codigo_emenda"].astype(str).str.slice(0, 4)
    df["ano_num"] = pd.to_numeric(df["ano"], errors="coerce")
    df = df[df["ano_num"] >= ano_min].copy()

    # Filtrar registros com dados bancários completos
    df_valid = df[
        df["cnpj_municipio"].notna() &
        df["codigo_banco"].notna() &
        df["agencia_sem_dv"].notna() &
        df["conta_corrente_sem_dv"].notna() &
        (df["conta_corrente_sem_dv"].str.strip() != "")
    ].copy()

    logger.info(f"Total de emendas carregadas com conta corrente (>= {ano_min}): {len(df_valid)}")
    return df_valid


def main():
    parser = argparse.ArgumentParser(
        description="Atualizador da base de pagamentos a fornecedores PJ de Emendas PIX em SC"
    )
    parser.add_argument(
        "--ano-min", type=int, default=2020,
        help="Ano inicial das emendas parlamentares (padrão: 2020)"
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="Número de requisições concorrentes (padrão: 8)"
    )
    parser.add_argument(
        "--limite", type=int, default=None,
        help="Limita o número de contas consultadas (útil para testes)"
    )
    parser.add_argument(
        "--no-sync-contas", action="store_true",
        help="Desativa a verificação automática de novas contas bancárias na API do Transferegov"
    )
    parser.add_argument(
        "--dias-expiracao", type=int, default=30,
        help="Validade máxima do cache de extratos em dias (padrão: 30 dias)"
    )
    parser.add_argument(
        "--cache", type=str, default=os.path.join("temp", "cache_extratos.json"),
        help="Caminho do arquivo de cache para retomada (padrão: temp/cache_extratos.json)"
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Ignora o arquivo de cache existente e reprocessa todas as contas"
    )
    parser.add_argument(
        "--output", type=str, default=os.path.join("dados", "pagamentos_pj.csv"),
        help="Caminho do arquivo de saída CSV (padrão: dados/pagamentos_pj.csv)"
    )
    parser.add_argument(
        "--input", type=str, default=os.path.join("dados", "emendas_sc.csv"),
        help="Caminho do arquivo de entrada de emendas (padrão: dados/emendas_sc.csv)"
    )

    args = parser.parse_args()

    # Criar sessão HTTP reutilizável
    session = create_session()

    # 1. Carregar emendas e sincronizar novas contas
    df_emendas = load_emendas_data(
        args.input,
        session=session,
        sync_contas=not args.no_sync_contas,
        ano_min=args.ano_min
    )

    # 2. Mapear contas bancárias únicas
    def account_key(row):
        return (
            clean_digits(row["cnpj_municipio"]).zfill(14),
            clean_digits(row["codigo_banco"]),
            clean_digits(row["agencia_sem_dv"]),
            clean_digits(row["conta_corrente_sem_dv"])
        )

    df_emendas["account_key"] = df_emendas.apply(account_key, axis=1)

    accounts_to_emendas = {}
    for _, row in df_emendas.iterrows():
        k = row["account_key"]
        if not all(k):
            continue
        if k not in accounts_to_emendas:
            accounts_to_emendas[k] = []
        accounts_to_emendas[k].append(row)

    unique_keys = list(accounts_to_emendas.keys())
    if args.limite:
        unique_keys = unique_keys[:args.limite]
        logger.info(f"Modo de teste: limitando processamento a {args.limite} contas únicas.")

    total_unique = len(unique_keys)
    logger.info(f"Total de contas bancárias únicas a processar: {total_unique}")

    # 3. Gerenciar Cache / Checkpoint com Expiração Temporal (TTL)
    os.makedirs(os.path.dirname(args.cache), exist_ok=True)
    cache_data = {}
    now = time.time()
    max_age_seconds = args.dias_expiracao * 86400  # converter dias para segundos

    if not args.no_cache and os.path.exists(args.cache):
        try:
            file_mtime = os.path.getmtime(args.cache)
            with open(args.cache, "r", encoding="utf-8") as f:
                raw_cache = json.load(f)

            # Normalizar cache para garantir formato com {"updated_at": ..., "transactions": ...}
            for k_str, val in raw_cache.items():
                if isinstance(val, dict) and "transactions" in val:
                    cache_data[k_str] = val
                elif isinstance(val, list):
                    # Formato legado: assume o mtime do arquivo
                    cache_data[k_str] = {
                        "updated_at": file_mtime,
                        "transactions": val
                    }
            logger.info(f"Cache carregado: {len(cache_data)} contas registradas no arquivo.")
        except Exception as e:
            logger.warning(f"Não foi possível ler o cache ({e}). Iniciando do zero.")
            cache_data = {}

    # Avaliar contas válidas vs expiradas
    keys_to_fetch = []
    valid_cache_count = 0
    expired_cache_count = 0

    for k in unique_keys:
        ckey = ":".join(k)
        if ckey not in cache_data:
            keys_to_fetch.append(k)
        else:
            entry = cache_data[ckey]
            updated_at = entry.get("updated_at", 0)
            if (now - updated_at) > max_age_seconds:
                expired_cache_count += 1
                keys_to_fetch.append(k)
            else:
                valid_cache_count += 1

    new_accounts_count = len(keys_to_fetch) - expired_cache_count
    logger.info(
        f"Status do Cache: {valid_cache_count} válidas (< {args.dias_expiracao} dias) | "
        f"{expired_cache_count} expiradas (>= {args.dias_expiracao} dias) | "
        f"{new_accounts_count} novas sem histórico."
    )
    logger.info(f"Total de contas que serão consultadas na API: {len(keys_to_fetch)}")

    # 4. Consultar API com ThreadPoolExecutor para contas pendentes/expiradas
    if keys_to_fetch:
        completed_fetch = 0
        total_fetch = len(keys_to_fetch)

        def worker_fetch(k):
            cnpj_muni, banco, agencia, conta = k
            txs = fetch_account_transactions(session, cnpj_muni, banco, agencia, conta)
            return k, txs

        logger.info(f"Iniciando requisições paralelas com {args.workers} workers...")
        last_save_time = time.time()

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_key = {executor.submit(worker_fetch, k): k for k in keys_to_fetch}

            for future in as_completed(future_to_key):
                k = future_to_key[future]
                try:
                    key_res, txs = future.result()
                    cache_key = ":".join(key_res)
                    cache_data[cache_key] = {
                        "updated_at": time.time(),
                        "transactions": txs
                    }
                except Exception as e:
                    logger.error(f"Erro ao processar conta {k}: {e}")
                    cache_data[":".join(k)] = {
                        "updated_at": time.time(),
                        "transactions": []
                    }

                completed_fetch += 1
                if completed_fetch % 50 == 0 or completed_fetch == total_fetch:
                    pct = (completed_fetch / total_fetch) * 100
                    logger.info(f"Progresso: [{completed_fetch}/{total_fetch}] ({pct:.1f}%) contas consultadas.")

                # Salvar cache periodicamente a cada 30 segundos
                if time.time() - last_save_time > 30:
                    with open(args.cache, "w", encoding="utf-8") as f:
                        json.dump(cache_data, f)
                    last_save_time = time.time()

        # Salvar cache final
        with open(args.cache, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)
        logger.info(f"Consultas finalizadas e salvas no cache ({args.cache}).")

    # 5. Processar transações e consolidar pagamentos a PJs com rateio proporcional em contas compartilhadas
    logger.info("Consolidando lançamentos de pagamentos a pessoas jurídicas com rateio proporcional...")
    records = []

    for k in unique_keys:
        cache_key = ":".join(k)
        entry = cache_data.get(cache_key, {})
        txs = entry.get("transactions", []) if isinstance(entry, dict) else entry
        emenda_rows = accounts_to_emendas.get(k, [])

        if not txs or not emenda_rows:
            continue

        # Filtrar apenas transações para PJs
        pj_txs = [tx for tx in txs if is_pj_transaction(tx)]
        if not pj_txs:
            continue

        # Deduplicar emendas da conta por código do plano de ação para evitar duplicações internas
        unique_planos = {}
        for er in emenda_rows:
            cpa = str(er.get("codigo_plano_acao", "")).strip()
            if cpa and cpa not in unique_planos:
                unique_planos[cpa] = er
            elif not cpa:
                unique_planos[id(er)] = er
        emendas_da_conta = list(unique_planos.values())

        def parse_emenda_val(row_dict):
            try:
                v = row_dict.get("valor_emenda")
                return float(v) if v is not None and str(v).strip() != "" else 0.0
            except (ValueError, TypeError):
                return 0.0

        total_valor_emendas_conta = sum(parse_emenda_val(er) for er in emendas_da_conta)
        num_emendas_conta = len(emendas_da_conta)
        is_conta_compartilhada = num_emendas_conta > 1

        # Associar os pagamentos às emendas vinculadas a esta conta com rateio proporcional
        for em_row in emendas_da_conta:
            cod_plano = str(em_row.get("codigo_plano_acao", "")).strip()
            raw_emenda = str(em_row.get("codigo_emenda", "")).strip()
            cod_emenda = raw_emenda[:12] if len(raw_emenda) >= 12 else raw_emenda
            nome_muni = str(em_row.get("nome_municipio", "")).strip()
            autor = str(em_row.get("nome_parlamentar", "")).strip()

            val_emenda_indiv = parse_emenda_val(em_row)
            if total_valor_emendas_conta > 0:
                peso = val_emenda_indiv / total_valor_emendas_conta
            else:
                peso = 1.0 / num_emendas_conta if num_emendas_conta > 0 else 1.0

            for tx in pj_txs:
                doc_raw = tx.get("doc_favorecido_gestao_financeira")
                cnpj_fav = standardize_cnpj(doc_raw)
                razao_social = str(tx.get("nome_favorecido_gestao_financeira", "")).strip()
                valor_debito = float(tx.get("valor_gestao_financeira") or 0.0)

                if valor_debito > 0 and cnpj_fav and razao_social:
                    valor_rateado = valor_debito * peso
                    records.append({
                        "Código do Plano de Ação": cod_plano,
                        "Código da Emenda": cod_emenda,
                        "Nome do Município": nome_muni,
                        "Autor da Emenda": autor,
                        "Banco": str(em_row.get("banco", "")).strip(),
                        "Agência": str(em_row.get("agencia", "")).strip(),
                        "Conta Corrente": str(em_row.get("conta_corrente", "")).strip(),
                        "CNPJ do beneficiário do pagamento": cnpj_fav,
                        "Razão Social": razao_social,
                        "valor_pago": valor_rateado,
                        "Conta Compartilhada": "Sim" if is_conta_compartilhada else "Não"
                    })

    if not records:
        logger.warning("Nenhum lançamento PJ identificado para exportação.")
        return

    df_result = pd.DataFrame(records)

    # 6. Agrupar somando os pagamentos por emenda e empresa
    group_cols = [
        "Código do Plano de Ação",
        "Código da Emenda",
        "Nome do Município",
        "Autor da Emenda",
        "Banco",
        "Agência",
        "Conta Corrente",
        "CNPJ do beneficiário do pagamento",
        "Razão Social",
        "Conta Compartilhada"
    ]
    df_consolidado = df_result.groupby(group_cols, as_index=False).agg({"valor_pago": "sum"})
    df_consolidado["valor_pago"] = df_consolidado["valor_pago"].round(2)

    df_consolidado.rename(columns={"valor_pago": "Valor Total Pago"}, inplace=True)
    df_consolidado.sort_values(
        by=["Nome do Município", "Código da Emenda", "Valor Total Pago"],
        ascending=[True, True, False],
        inplace=True
    )

    # 7. Backup de segurança e exportação do arquivo final
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    if os.path.exists(args.output):
        backup_path = f"{args.output}.bak"
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(args.output, backup_path)
            logger.info(f"Backup do arquivo anterior salvo em: {backup_path}")
        except Exception as e:
            logger.warning(f"Não foi possível criar backup ({e}). Prosseguindo com gravação direta.")

    df_consolidado.to_csv(args.output, sep=";", index=False, encoding="utf-8")

    logger.info("=" * 60)
    logger.info("🎉 ATUALIZAÇÃO CONCLUÍDA COM SUCESSO!")
    logger.info(f"Destino: {args.output}")
    logger.info(f"Total de registros de pagamentos PJ gerados: {len(df_consolidado):,}")
    logger.info(f"Total pago consolidado: R$ {df_consolidado['Valor Total Pago'].sum():,.2f}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
