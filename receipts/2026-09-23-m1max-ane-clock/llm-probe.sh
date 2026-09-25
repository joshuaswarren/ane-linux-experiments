#!/bin/bash
# Real completion against llm-inference.service (:8002); key read from the
# unit, never printed.
kf=$(grep -oP -- '--api-key-file[ =]\K\S+' /etc/systemd/system/llm-inference.service)
key=$(tr -d '[:space:]' < "$kf")
for i in $(seq 1 60); do
	curl -sf -m 3 http://127.0.0.1:8002/health >/dev/null && break
	sleep 5
done
curl -s -m 5 http://127.0.0.1:8002/health; echo
curl -s -m 180 http://127.0.0.1:8002/v1/chat/completions \
	-H "Authorization: Bearer $key" -H 'Content-Type: application/json' \
	-d '{"messages":[{"role":"user","content":"Reply with the single word: Pacific"}],"max_tokens":256,"temperature":0}' |
	python3 -c 'import json,sys; r=json.load(sys.stdin); c=r["choices"][0]; print("finish=%s content=%r" % (c["finish_reason"], c["message"].get("content")))'
