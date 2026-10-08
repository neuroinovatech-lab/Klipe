import unittest

import skia

from motioncore.cena import Cena, validar


class NumeroLayerTest(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "duracao": 5,
            "camadas": [{
                "tipo": "numero",
                "valor": [[0, 0, "linear"], [5, 1000]],
                "prefixo": "R$ ",
                "casas": 2,
                "separador_milhar": ".",
                "separador_decimal": ",",
                "fonte": "Arial",
                "peso": 700,
            }],
        }

    def test_formata_pt_br(self):
        cena = Cena(self.spec, 1280, 720)
        bloco = next(iter(cena._blocos.values()))
        self.assertEqual(bloco.format(0), "R$ 0,00")
        self.assertEqual(bloco.format(1000), "R$ 1.000,00")

    def test_valor_participa_da_assinatura_e_desenha(self):
        cena = Cena(self.spec, 1280, 720)
        self.assertNotEqual(cena.assinatura(0), cena.assinatura(5))
        surface = skia.Surface(1280, 720)
        cena.desenhar(surface.getCanvas(), 2.5)

    def test_valor_e_obrigatorio(self):
        erros = validar({"camadas": [{"tipo": "numero"}]})
        self.assertTrue(any("sem 'valor'" in erro for erro in erros))


if __name__ == "__main__":
    unittest.main()
