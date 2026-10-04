-- Recurso sem coleta bem-sucedida dentro do limite de erro da sua cadência: o vigia avisa.
select recurso_id, cadencia_corrente, ultimo_sucesso, atraso_horas, limite_erro_horas
from {{ ref('monitor_fontes') }}
where ultimo_sucesso is null or atraso_horas > limite_erro_horas
