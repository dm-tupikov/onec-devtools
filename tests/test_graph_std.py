"""Tests for graph_index.GraphIndex and std_search.StdCorpus."""

import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_devtools.parser_1c_xml import OneCConfigParser
from mcp_devtools.graph_index import GraphIndex
from mcp_devtools.std_search import StdCorpus


def make_dump(root: Path) -> Path:
    """Create a minimal standard-layout 1C dump with two objects and modules."""
    md = root / "src"
    # Catalogs/МойСправочник/ + Catalogs/МойСправочник.xml
    cat = md / "Catalogs" / "МойСправочник"
    (cat / "Ext").mkdir(parents=True)
    (cat / "Forms" / "ФормаЭлемента" / "Ext").mkdir(parents=True)
    cat_xml = md / "Catalogs" / "МойСправочник.xml"
    cat_xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
        '<Catalog uuid="00000000-0000-0000-0000-000000000001">'
        '<Properties><Name>МойСправочник</Name>'
        '<Synonym xmlns:v8="http://v8.1c.ru/8.1/data/core">'
        '<v8:item><v8:content>Мой справочник</v8:content></v8:item></Synonym>'
        '</Properties>'
        '<ChildObjects></ChildObjects>'
        '</Catalog></MetaDataObject>',
        encoding="utf-8",
    )
    (cat / "Ext" / "ObjectModule.bsl").write_text(
        "Процедура ОбработкаПроведения(Отказ, Режим)\n"
        "    Движения.МойРегистр.Записывать = Истина;\n"
        "    Запись = Движения.МойРегистр.Добавить();\n"
        "    Запись.Сумма = 1;\n"
        "КонецПроцедуры\n",
        encoding="utf-8",
    )
    # AccumulationRegisters/МойРегистр/
    reg = md / "AccumulationRegisters" / "МойРегистр"
    (reg / "Ext").mkdir(parents=True)
    (md / "AccumulationRegisters" / "МойРегистр.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
        '<AccumulationRegister uuid="00000000-0000-0000-0000-000000000002">'
        '<Properties><Name>МойРегистр</Name></Properties>'
        '<ChildObjects></ChildObjects>'
        '</AccumulationRegister></MetaDataObject>',
        encoding="utf-8",
    )
    (reg / "Ext" / "ManagerModule.bsl").write_text(
        "Функция ПолучитьОстатки()\n"
        "    Возврат Справочники.МойСправочник.НайтиПоНаименованию(\"тест\");\n"
        "КонецФункции\n",
        encoding="utf-8",
    )
    return md


class GraphIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.dump = make_dump(root)
        cls.parser = OneCConfigParser(str(cls.dump)).parse()
        cls.gi = GraphIndex(cls.parser).build()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_vertices_cover_objects(self):
        self.assertIn("Catalog:МойСправочник", self.gi.vertices)
        self.assertIn("AccumulationRegister:МойРегистр", self.gi.vertices)

    def test_module_owner_resolved(self):
        owners = {self.gi.module_owner[p] for p in self.gi.module_owner}
        self.assertIn("Catalog:МойСправочник", owners)
        self.assertIn("AccumulationRegister:МойРегистр", owners)

    def test_movement_edge_document_to_register(self):
        # Движения.МойРегистр from the catalog object module -> register vertex
        targets = {e["target"] for e in self.gi.ref_edges if e.get("kind") == "movement"}
        self.assertIn("AccumulationRegister:МойРегистр", targets)
        mov = [e for e in self.gi.ref_edges if e.get("kind") == "movement" and e["target"] == "AccumulationRegister:МойРегистр"]
        self.assertTrue(all(e["from_owner"] == "Catalog:МойСправочник" for e in mov))

    def test_collection_edge_register_to_catalog(self):
        # Справочники.МойСправочник in the register manager module
        targets = {e["target"] for e in self.gi.ref_edges if e.get("kind") == "collection"}
        self.assertIn("Catalog:МойСправочник", targets)

    def test_impact_reverse_bfs(self):
        res = self.gi.impact("МойРегистр", obj_type="AccumulationRegister", depth=2)
        self.assertNotIn("error", res)
        keys = [a["key"] for a in res["affected"]]
        self.assertIn("Catalog:МойСправочник", keys)

    def test_calls_outgoing_with_resolution(self):
        res = self.gi.calls("МойРегистр", direction="out", obj_type="AccumulationRegister")
        self.assertNotIn("error", res)
        # ПолучитьОстатки calls НайтиПоНаименованию (platform method — unresolved is fine)
        callees = {e["callee"] for e in res["outgoing"]}
        self.assertIn("НайтиПоНаименованию", callees)

    def test_unique_name_resolves_without_type(self):
        res = self.gi.calls("МойСправочник")
        self.assertNotIn("error", res)
        self.assertEqual(res["object"], "Catalog:МойСправочник")

    def test_search_by_name_fragment(self):
        res = self.gi.search("Справочник")
        self.assertTrue(any(h["key"] == "Catalog:МойСправочник" for h in res["hits"]))


class StdCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.jsonl = root / "pages.jsonl"
        rec = {
            "id": "#std999",
            "title": "Тестовый стандарт",
            "aliases": ["std999", "стандарт 999", "Транзакции в цикле"],
            "body_markdown": "ID: #std999\n\n# Тестовый стандарт\n\nНе выполняйте транзакции в цикле.",
        }
        cls.jsonl.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
        cls.corpus = StdCorpus(str(cls.jsonl)).load()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_load(self):
        self.assertEqual(self.corpus.stats()["pages"], 1)

    def test_get_by_id_variants(self):
        for variant in ("#std999", "std999", "999", "std 999"):
            body = self.corpus.body(variant)
            self.assertIsNotNone(body, f"failed for {variant}")
            self.assertEqual(body["id"], "#std999")

    def test_search_alias_hit(self):
        hits = self.corpus.search("транзакции в цикле")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "#std999")

    def test_search_fulltext(self):
        hits = self.corpus.search("не выполняйте транзакции")
        self.assertTrue(hits)

    def test_get_missing(self):
        self.assertIsNone(self.corpus.get("std404"))


if __name__ == "__main__":
    unittest.main()
