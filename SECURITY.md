# Segurança

## Como relatar uma vulnerabilidade

Não abra issue pública. Use o relato privado do GitHub (aba **Security** → **Report a vulnerability**)
e descreva o problema, como reproduzir e o impacto. A resposta inicial sai em até 7 dias.

## Dados pessoais

Os dados publicados (marts no R2) vêm de fontes oficiais abertas. O CPF nunca é publicado completo:
os marts trazem só a máscara (`***.456.789-**`), e um teste do dbt barra qualquer CPF completo antes
da publicação. O dado bruto fica no bucket privado do GCS e, no cache do GitHub Actions, sempre cifrado.
Se encontrar um dado pessoal exposto indevidamente, relate pelo mesmo canal.
