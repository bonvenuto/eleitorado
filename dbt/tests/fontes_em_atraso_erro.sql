-- Recurso cuja última coleta bem-sucedida passou do limite de erro da cadência: o workflow falha.
-- Recurso que nunca teve sucesso (carga inicial em andamento) fica só no teste de aviso.
select recurso_id, cadencia_corrente, ultimo_sucesso, atraso_horas, limite_erro_horas
from {{ ref('monitor_fontes') }}
where atraso_horas > limite_erro_horas

