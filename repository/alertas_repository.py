import logging

import psycopg2

from core.tipo_deteccao import tipos_do_filtro, validar_vinculo_alerta
from models.alertas import Alerta

logger = logging.getLogger(__name__)


class AlertasRepository:
    _SELECT = """
        SELECT a.id_alerta, a.resolvido, a.data_hora, a.id_monitorar,
               a.id_usuario, a.evento, a.severidade, m.id_zona,
               COALESCE(a.id_camera, z.id_camera), m.id_epi, a.tipo_deteccao
        FROM alertas a
        LEFT JOIN monitorar m ON m.id_monitorar = a.id_monitorar
        LEFT JOIN zonas z ON m.id_zona = z.id_zona
    """

    def __init__(self, connection):
        self.conn = connection

    @staticmethod
    def _mapear_alerta(row) -> Alerta:
        return Alerta(
            id=row[0], resolvido=row[1],
            data_hora=row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else '',
            id_monitorar=row[3], id_usuario=row[4], evento=row[5],
            severidade=row[6], id_zona=row[7], id_camera=row[8],
            id_epi=row[9], tipo_deteccao=row[10],
        )

    def _consultar(self, condicao: str | None = None, parametros: tuple = (),
                   tipo: str | None = None) -> list[Alerta]:
        # condicao is supplied only by the fixed queries below, never by HTTP input.
        filtros = [condicao] if condicao else []
        tipos = tipos_do_filtro(tipo)
        if tipos is not None:
            filtros.append('a.tipo_deteccao IN %s')
            parametros += (tipos,)
        query = self._SELECT
        if filtros:
            query += ' WHERE ' + ' AND '.join(filtros)
        with self.conn.cursor() as cursor:
            cursor.execute(query, parametros)
            return [self._mapear_alerta(row) for row in cursor.fetchall()]

    def get_alertas(self, tipo: str | None = None) -> list[Alerta]:
        return self._consultar(tipo=tipo)

    def get_alertas_por_id_camera(self, id_camera: int, tipo: str | None = None) -> list[Alerta]:
        return self._consultar('COALESCE(a.id_camera, z.id_camera) = %s', (id_camera,), tipo)

    def get_alertas_por_id_zona(self, id_zona: int, tipo: str | None = None) -> list[Alerta]:
        return self._consultar('m.id_zona = %s', (id_zona,), tipo)

    def get_alerta_por_id(self, id_alerta: int) -> Alerta | None:
        alertas = self._consultar('a.id_alerta = %s', (id_alerta,))
        return alertas[0] if alertas else None

    def get_alertas_por_id_usuario(self, id_usuario: int) -> list[Alerta]:
        return self._consultar('a.id_usuario = %s', (id_usuario,))

    def marcar_alerta_resolvido(self, id_alerta: int) -> bool:
        with self.conn.cursor() as cursor:
            query = "UPDATE alertas SET resolvido = TRUE WHERE id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            self.conn.commit()

            return cursor.rowcount > 0

    def criar_alerta(self, id_monitorar: int | None, id_usuario: int | None,
                     evento: str, severidade: int = 1, *,
                     tipo_deteccao: str = 'epi', id_camera: int | None = None) -> bool:
        validar_vinculo_alerta(tipo_deteccao, id_monitorar, id_camera)
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO alertas
                       (resolvido, data_hora, id_monitorar, id_usuario, evento,
                        severidade, tipo_deteccao, id_camera)
                       VALUES (FALSE, NOW(), %s, %s, %s, %s, %s, %s)""",
                    (id_monitorar, id_usuario, evento, severidade, tipo_deteccao, id_camera),
                )
                sucesso = cursor.rowcount > 0
            self.conn.commit()
            return sucesso
        except psycopg2.Error as exc:
            self.conn.rollback()
            logger.warning('Falha ao salvar alerta (SQLSTATE %s).', exc.pgcode)
            return False

    def deletar_alerta(self, id_alerta: int) -> bool:
        with self.conn.cursor() as cursor:
            query = "DELETE FROM alertas WHERE id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            self.conn.commit()

            return cursor.rowcount > 0

    def get_contagem_por_tipo_epi(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            query = """
                SELECT COALESCE(e.categoria, 'Sem Categoria') AS categoria, COUNT(*) AS total
                FROM alertas a
                JOIN monitorar m ON m.id_monitorar = a.id_monitorar
                LEFT JOIN epis e ON e.id_epi = m.id_epi
                WHERE a.tipo_deteccao = 'epi'
                GROUP BY COALESCE(e.categoria, 'Sem Categoria')
                ORDER BY total DESC;
            """

            cursor.execute(query)
            resultados = cursor.fetchall()

            valores: list[dict] = []

            for categoria, total in resultados:
                valores.append({
                    "categoria": categoria,
                    "total": total
                })

            return valores

    def get_contagem_por_periodo(self, desde) -> list[dict]:
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT DATE(a.data_hora) AS dia, COUNT(*) AS total
                    FROM alertas a
                    WHERE a.data_hora >= %s
                    GROUP BY DATE(a.data_hora)
                    ORDER BY dia ASC;
                """

                cursor.execute(query, (desde,))
                resultados = cursor.fetchall()

                valores: list[dict] = []

                for dia, total in resultados:
                    valores.append({
                        "dia": dia.strftime("%Y-%m-%d"),
                        "total": total
                    })

                return valores
        except psycopg2.Error:
            self.conn.rollback()
            raise

    def get_monitoramento_por_id_alerta(self, id_alerta: int) -> dict | None:
        with self.conn.cursor() as cursor:
            query = "SELECT m.id_monitorar, m.id_zona, m.id_epi FROM monitorar m JOIN alertas a ON m.id_monitorar = a.id_monitorar WHERE a.id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            monitoramento = cursor.fetchone()

            if monitoramento:
                return {
                    'id_monitorar': monitoramento[0],
                    'id_zona': monitoramento[1],
                    'id_epi': monitoramento[2]
                }
            else:
                return None