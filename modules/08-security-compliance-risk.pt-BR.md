# Módulo 8: Segurança, compliance e risco

**Semana 10** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](08-security-compliance-risk.md)

## Objetivo

Aplicar segurança onde o dinheiro passa: gestão e rotação de chaves, envelope encryption, escopo de PCI/LGPD, limites e antifraude.

## Segunda a quarta: leitura + laboratório (3 h por dia)

| Dia | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- |
| Seg | Hashing x criptografia x HMAC; TLS e mTLS entre serviços e com parceiros.<br>KMS e HSM, envelope encryption (documentação da AWS KMS), rotação de chaves. | Vault em modo dev (ou LocalStack KMS) no Compose; criptografar e descriptografar pela CLI. |
| Ter | OWASP API Security Top 10 (2023).<br>PCI DSS Quick Reference Guide e tokenização; LGPD art. 7, 16 e 18 (exclusão x obrigação de guardar registro financeiro). | Threat model STRIDE: diagrama de fluxo de dados do sistema e lista de ameaças (rascunho do docs/m08.md). |
| Qua | RFC 9700 (OAuth 2.0 Security BCP), riscos de JWT, autorização por recurso (BOLA).<br>Antifraude e limites (velocity checks), KYC/AML e regulação do Bacen em alto nível. | Preparação do dia de conclusão: cliente de webhook de teste e lista de tarefas. Sem código do TCM. |

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (1 h) Assinatura de webhook com kid e duas chaves ativas; endpoint público com as chaves de verificação.
2. (1 h) Rotação: nova chave, sobreposição, aposentar a antiga; teste com cliente ativo sem falha de verificação.
3. (1 h) Envelope encryption do CPF: chave de dados por registro, chave mestra no Vault/KMS.
4. (30 min) Redação de CPF, cartão e tokens nos logs.
5. (1 h) Serviço de limites e velocity check com timeout e fallback definido.
6. (30 min) docs/m08.md final.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Rotacionar a chave de assinatura com um cliente de webhook ativo não gera nenhuma falha de verificação.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Onde ficam as chaves que assinam os webhooks que você envia, e como você as rotaciona sem derrubar os clientes?
