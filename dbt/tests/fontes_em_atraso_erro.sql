-- Recurso do grupo diário cuja última coleta bem-sucedida passou do limite de erro da cadência:
-- o workflow falha. Grupos fora do pipeline diário (receita, tse) ficam apenas em aviso, e
-- recursos que nunca tiveram sucesso ficam só no teste de aviso.
select recurso_id, grupo, cadencia_corrente, ultimo_sucesso, atraso_horas, limite_erro_horas
from {{ ref('monitor_fontes') }}
where grupo = 'diario' and atraso_horas > limite_erro_horas

