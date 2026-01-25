{{- define "traffic-manager.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "traffic-manager.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name -}}
{{- end -}}
{{- end -}}

{{- define "traffic-manager.labels" -}}
app.kubernetes.io/name: {{ include "traffic-manager.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: traffic-manager
{{- end -}}

{{- define "traffic-manager.selectorLabels" -}}
app.kubernetes.io/name: {{ include "traffic-manager.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "traffic-manager.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- if .Values.serviceAccount.name -}}
{{- .Values.serviceAccount.name -}}
{{- else -}}
{{- include "traffic-manager.fullname" . -}}
{{- end -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
