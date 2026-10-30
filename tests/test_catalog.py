from pianji.catalog import Catalog

def test_catalog_survives_reopen(tmp_path):
    cat=Catalog(tmp_path)
    a=cat.activity('中文 活动')
    assert {p['name'] for p in cat.people(a['id'])}=={'合照','待分类'}
    assert Catalog(tmp_path).activities()[0]['id']==a['id']
