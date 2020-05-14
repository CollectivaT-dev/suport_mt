mongoexport -d suportmutu -c ar -o suportmutu_ar.json
mongoexport -d suportmutu -c ur -o suportmutu_ur.json
mongoexport -d suportmutu -c zh-CN -o suportmutu_zh.json
tar czf backup_`date +"%Y%m%d"`.tar.gz suportmutu*.json
