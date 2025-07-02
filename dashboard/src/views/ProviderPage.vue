<template>
    <v-card style="height: 100%;">
        <v-card-text style="padding: 32px; height: 100%;">

            <v-menu>
                <template v-slot:activator="{ props }">
                    <v-btn class="flex-grow-1" variant="tonal" @click="new_provider_dialog = true" size="large"
                        rounded="lg" v-bind="props" color="primary">
                        <template v-slot:default>
                            <v-icon>mdi-plus</v-icon>
                            新增服务提供商
                        </template>
                    </v-btn>
                </template>
                <v-list @update:selected="addFromDefaultConfigTmpl($event)">
                    <v-list-item
                        v-for="(item, index) in metadata['provider_group']['metadata']['provider'].config_template"
                        :key="index" rounded="xl" :value="index">
                        <v-list-item-title>{{ index }}</v-list-item-title>
                    </v-list-item>
                </v-list>
            </v-menu>
            <v-row style="margin-top: 16px;">
                <v-col v-for="(provider, index) in config_data['provider']" :key="index" cols="12" md="6" lg="3">
                    <v-card class="fade-in" style="margin-bottom: 16px; min-height: 250px; max-height: 250px; display: flex; justify-content: space-between; flex-direction: column;">
                        <v-card-title class="d-flex justify-space-between align-center">
                            <span class="text-h4">{{ provider.id }}</span>
                            <v-switch color="primary" hide-details density="compact" v-model="provider['enable']"
                                @update:modelValue="providerStatusChange(provider)"></v-switch>
                        </v-card-title>
                        <v-card-text>
                            <div>
                                <span style="font-size:12px">适配器类型: </span> <v-chip size="small" color="primary" text>{{ provider.type }}</v-chip>
                            </div>
                            <div v-if="provider?.api_base" style="margin-top: 8px;">
                                <span style="font-size:12px">API Base: </span> <v-chip size="small" color="primary" text>{{ provider?.api_base }}</v-chip>
                            </div>
                        </v-card-text>
                        <v-card-actions class="d-flex justify-end">
                            <v-btn color="error" text @click="deleteprovider(provider.id);">
                                删除
                            </v-btn>
                            <v-btn color="blue-darken-1" text
                                @click="updatingMode = true; showproviderCfg = true; newSelectedproviderConfig = provider; newSelectedproviderName = provider.id">
                                配置
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-col>
            </v-row>
            <v-dialog v-model="showproviderCfg" width="700">
                <v-card>
                    <v-card-title>
                        <span class="text-h4">{{ newSelectedproviderName }} 配置</span>
                    </v-card-title>
                    <v-card-text>
                        <AstrBotConfig :iterable="newSelectedproviderConfig"
                            :metadata="metadata['provider_group']['metadata']" metadataKey="provider" />
                    </v-card-text>
                    <v-card-actions>
                        <v-spacer></v-spacer>
                        <v-btn color="blue-darken-1" variant="text" @click="newprovider" :loading="loading">
                            保存
                        </v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>

            <v-btn style="margin-top: 16px" class="flex-grow-1" variant="tonal"  size="large" rounded="lg" color="gray" @click="showConsole = !showConsole">
                <template v-slot:default>
                    <v-icon>mdi-console-line</v-icon>
                    {{ showConsole ? '隐藏' : '显示' }}日志
                </template>
            </v-btn>

            <div v-if="showConsole" style="margin-top: 32px; ">
                <ConsoleDisplayer style="background-color: #fff; height: 300px"></ConsoleDisplayer>
            </div>



        </v-card-text>
    </v-card>

    <v-snackbar :timeout="3000" elevation="24" :color="save_message_success" v-model="save_message_snack">
        {{ save_message }}
    </v-snackbar>
    <WaitingForRestart ref="wfr"></WaitingForRestart>
</template>
<script>

import axios from 'axios';
import AstrBotConfig from '@/components/shared/AstrBotConfig.vue';
import WaitingForRestart from '@/components/shared/WaitingForRestart.vue';
import ConsoleDisplayer from '@/components/shared/ConsoleDisplayer.vue';

export default {
    name: 'ProviderPage',
    components: {
        AstrBotConfig,
        WaitingForRestart,
        ConsoleDisplayer
    },
    data() {
        return {
            config_data: {},
            fetched: false,
            metadata: {},
            showproviderCfg: false,

            newSelectedproviderName: '',
            newSelectedproviderConfig: {},
            updatingMode: false,

            loading: false,

            save_message_snack: false,
            save_message: "",
            save_message_success: "",

      showConsole: false,
      
      // 供应商状态相关
      providerStatuses: [],
      loadingStatus: false,

      // 新增提供商对话框相关
      showAddProviderDialog: false,
      activeProviderTab: 'chat_completion',

      // 添加提供商类型分类
      activeProviderTypeTab: 'all',

      // 兼容旧版本（< v3.5.11）的 mapping，用于映射到对应的提供商能力类型
      oldVersionProviderTypeMapping: {
        "openai_chat_completion": "chat_completion",
        "anthropic_chat_completion": "chat_completion",
        "googlegenai_chat_completion": "chat_completion",
        "zhipu_chat_completion": "chat_completion",
        "dify": "chat_completion",
        "dashscope": "chat_completion",
        "openai_whisper_api": "speech_to_text",
        "openai_whisper_selfhost": "speech_to_text",
        "sensevoice_stt_selfhost": "speech_to_text",
        "cosyvoice_tts_selfhost": "text_to_speech",
        "openai_tts_api": "text_to_speech",
        "edge_tts": "text_to_speech",
        "gsvi_tts_api": "text_to_speech",
        "fishaudio_tts_api": "text_to_speech",
        "dashscope_tts": "text_to_speech",
        "azure_tts": "text_to_speech",
        "minimax_tts_api": "text_to_speech",
        "volcengine_tts": "text_to_speech",
      }
    }
  },

  watch: {
    showIdConflictDialog(newValue) {
      // 当对话框关闭时，如果 Promise 还在等待，则拒绝它以防止内存泄漏
      if (!newValue && this.idConflictResolve) {
        this.idConflictResolve(false);
        this.idConflictResolve = null;
      }
    },
    showKeyConfirm(newValue) {
      // 当对话框关闭时，如果 Promise 还在等待，则拒绝它以防止内存泄漏
      if (!newValue && this.keyConfirmResolve) {
        this.keyConfirmResolve(false);
        this.keyConfirmResolve = null;
      }
    }
  },

  computed: {
    // 翻译消息的计算属性
    messages() {
      return {
        emptyText: {
          all: this.tm('providers.empty.all'),
          typed: this.tm('providers.empty.typed')
        },
        tabTypes: {
          'chat_completion': this.tm('providers.tabs.chatCompletion'),
          'speech_to_text': this.tm('providers.tabs.speechToText'),
          'text_to_speech': this.tm('providers.tabs.textToSpeech'),
          'embedding': this.tm('providers.tabs.embedding')
        },
        success: {
          update: this.tm('messages.success.update'),
          add: this.tm('messages.success.add'),
          delete: this.tm('messages.success.delete'),
          statusUpdate: this.tm('messages.success.statusUpdate'),
          sessionSeparation: this.tm('messages.success.sessionSeparation')
        },
        error: {
          sessionSeparation: this.tm('messages.error.sessionSeparation')
        },
        confirm: {
          delete: this.tm('messages.confirm.delete')
        }
      };
    },
    
    // 根据选择的标签过滤提供商列表
    filteredProviders() {
      if (!this.config_data.provider || this.activeProviderTypeTab === 'all') {
        return this.config_data.provider || [];
      }

      return this.config_data.provider.filter(provider => {
        // 如果provider.provider_type已经存在，直接使用它
        if (provider.provider_type) {
          return provider.provider_type === this.activeProviderTypeTab;
        }
        
        // 否则使用映射关系
        const mappedType = this.oldVersionProviderTypeMapping[provider.type];
        return mappedType === this.activeProviderTypeTab;
      });
    }
  },

    mounted() {
        this.getConfig();
    },

    methods: {
        getConfig() {
            // 获取配置
            axios.get('/api/config/get').then((res) => {
                this.config_data = res.data.data.config;
                this.fetched = true
                this.metadata = res.data.data.metadata;
            }).catch((err) => {
                save_message = err;
                save_message_snack = true;
                save_message_success = "error";
            });
        },

        addFromDefaultConfigTmpl(index) {
            // 从默认配置模板中添加
            console.log(index);
            this.newSelectedproviderName = index[0];
            this.showproviderCfg = true;
            this.updatingMode = false;
            this.newSelectedproviderConfig = this.metadata['provider_group']['metadata']['provider'].config_template[index[0]];
        },

        newprovider() {
            // 新建或者更新平台
            this.loading = true;
            if (this.updatingMode) {
                axios.post('/api/config/provider/update', {
                    id: this.newSelectedproviderName,
                    config: this.newSelectedproviderConfig
                }).then((res) => {
                    this.loading = false;
                    this.showproviderCfg = false;
                    this.getConfig();
                    // this.$refs.wfr.check();
                    this.save_message = res.data.message;
                    this.save_message_snack = true;
                    this.save_message_success = "success";
                }).catch((err) => {
                    this.loading = false;
                    this.save_message = err;
                    this.save_message_snack = true;
                    this.save_message_success = "error";
                });
                this.updatingMode = false;
            } else {
                axios.post('/api/config/provider/new', this.newSelectedproviderConfig).then((res) => {
                    this.loading = false;
                    this.showproviderCfg = false;
                    this.getConfig();
                }).catch((err) => {
                    this.loading = false;
                    this.save_message = err;
                    this.save_message_snack = true;
                    this.save_message_success = "error";
                });
            }
        },

        deleteprovider(provider_id) {
            // 删除平台
            axios.post('/api/config/provider/delete', { id: provider_id }).then((res) => {
                this.getConfig();
                // this.$refs.wfr.check();
                this.save_message = res.data.message;
                this.save_message_snack = true;
                this.save_message_success = "success";
            }).catch((err) => {
                this.save_message = err;
                this.save_message_snack = true;
                this.save_message_success = "error";
            });
        },

        providerStatusChange(provider) {
            // 平台状态改变
            axios.post('/api/config/provider/update', {
                id: provider.id,
                config: provider
            }).then((res) => {
                this.getConfig();
                // this.$refs.wfr.check();
                this.save_message = res.data.message;
                this.save_message_snack = true;
                this.save_message_success = "success";
            }).catch((err) => {
                this.save_message = err;
                this.save_message_snack = true;
                this.save_message_success = "error";
            });
        }

    }
}

</script>

<style>
@keyframes fadeIn {
    from {
        opacity: 0;
    }

    to {
        opacity: 1;
    }
}

.fade-in {
    animation: fadeIn 0.2s ease-in-out;
}
</style>