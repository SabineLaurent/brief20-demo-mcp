import json

from agent import format_tool_call, format_tool_result, load_servers


def test_load_servers_convertit_le_format_editeur_vers_langchain(tmp_path):
    fichier = tmp_path / "mcp.json"
    fichier.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "datagouv": {"type": "http", "url": "https://mcp.data.gouv.fr/mcp"}
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_servers(fichier) == {
        "datagouv": {
            "url": "https://mcp.data.gouv.fr/mcp",
            "transport": "streamable_http",
        }
    }


def test_format_tool_call_affiche_le_nom_et_les_arguments():
    resultat = format_tool_call("search_datasets", {"query": "bornes recharge"})
    assert resultat == "🔧 search_datasets(query='bornes recharge')"


def test_format_tool_call_tronque_les_arguments_trop_longs():
    resultat = format_tool_call("query_resource_data", {"resource_id": "x" * 200})
    assert len(resultat) < 100
    assert resultat.endswith("…)")


def test_format_tool_result_utilise_la_typographie_francaise():
    resultat = format_tool_result("x" * 7029, 0.81)
    assert resultat == "   ← 7 029 caractères en 0,8 s"
