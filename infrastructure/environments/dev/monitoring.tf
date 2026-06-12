# ──────────────────────────────────────────────────────────────────────────────
# Monitoring — metrics-server (kubectl top / HPA용 리소스 지표 수집)
#
# namespace: monitor (eks 모듈의 monitor Fargate 프로파일이 스케줄 보장)
# Fargate에서는 kubelet 인증서 검증이 안 되므로 --kubelet-insecure-tls 필요.
# ──────────────────────────────────────────────────────────────────────────────

resource "helm_release" "metrics_server" {
  name             = "metrics-server"
  repository       = "https://kubernetes-sigs.github.io/metrics-server/"
  chart            = "metrics-server"
  version          = "3.12.2"
  namespace        = "monitor"
  create_namespace = true

  # Fargate 호환: kubelet TLS 검증 생략 + InternalIP 우선
  set {
    name  = "args[0]"
    value = "--kubelet-insecure-tls"
  }
  set {
    name  = "args[1]"
    value = "--kubelet-preferred-address-types=InternalIP"
  }

  # [공식] EKS Fargate: metrics-server secure-port(=containerPort)가 Fargate kubelet
  # 10250과 충돌 → 노드 스크랩 403. 10251로 이동 (AWS re:Post eks-metrics-server-install).
  set {
    name  = "containerPort"
    value = "10251"
  }

  # 단일 replica로 충분 (프로토타입)
  set {
    name  = "replicas"
    value = "1"
  }

  # monitor 네임스페이스 Fargate 프로파일이 준비된 후 배포
  depends_on = [module.eks]
}
