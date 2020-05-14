mongoexport -d suportmutu -c ar -o suportmutu_ar_`date +"%Y%m%d"`.json
mongoexport -d suportmutu -c ur -o suportmutu_ur_`date +"%Y%m%d"`.json
mongoexport -d suportmutu -c zh-CN -o suportmutu_zh_`date +"%Y%m%d"`.json
