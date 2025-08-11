#  source ~/openai_clauder_cc.sh
#

run_make_emb:
	bash run/run_make_emb.sh

run_main:
	END=-1 USE_REAL_MODELS=true NUM_WORKERS=4 POOL_SIZE=2 ENABLE_REDIS=true  bash run/run_production.sh

