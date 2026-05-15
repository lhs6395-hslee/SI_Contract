"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Check, Save } from "lucide-react";

const STORAGE_KEY = "si_contract_defaults";
const FASTAPI_BASE = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

export interface DefaultRates {
  nationalPension: number;
  healthInsurance: number;
  industrialAccident: number;
  employmentInsurance: number;
  indirectRate: number;
  adminRate: number;
}

const INITIAL_RATES: DefaultRates = {
  nationalPension: 4.5,
  healthInsurance: 4.0041,
  industrialAccident: 0,
  employmentInsurance: 0,
  indirectRate: 0,
  adminRate: 0,
};

export function loadDefaultRates(): DefaultRates {
  if (typeof window === "undefined") return INITIAL_RATES;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...INITIAL_RATES, ...JSON.parse(raw) };
  } catch { /* */ }
  return INITIAL_RATES;
}

function saveDefaultRates(rates: DefaultRates) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(rates));
}

async function loadDefaultRatesAsync(): Promise<DefaultRates> {
  try {
    const res = await fetch(`${FASTAPI_BASE}/api/settings`);
    if (res.ok) {
      const data = await res.json();
      if (data.rates && Object.keys(data.rates).length > 0) {
        const merged = { ...INITIAL_RATES, ...data.rates };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
        return merged;
      }
    }
  } catch { /* fallback */ }
  return loadDefaultRates();
}

async function saveDefaultRatesAsync(rates: DefaultRates) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(rates));
  try {
    await fetch(`${FASTAPI_BASE}/api/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rates }),
    });
  } catch { /* 서버 접근 불가 */ }
}

export function SettingsPage() {
  const [rates, setRates] = useState<DefaultRates>(INITIAL_RATES);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadDefaultRatesAsync().then(setRates);
  }, []);

  const update = (key: keyof DefaultRates, val: string) => {
    const num = parseFloat(val);
    setRates((prev) => ({ ...prev, [key]: isNaN(num) ? 0 : num }));
    setSaved(false);
  };

  const doSave = () => {
    saveDefaultRatesAsync(rates);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const fields: { key: keyof DefaultRates; label: string; hint: string }[] = [
    { key: "nationalPension", label: "국민연금 (%)", hint: "사업주 부담분. 25년 기준 4.5%" },
    { key: "healthInsurance", label: "건강보험 (%)", hint: "사업주 부담분. 25년 기준 4.0041%" },
    { key: "industrialAccident", label: "산재보험 (%)", hint: "안전보건팀 공지 참조. 템플릿 이미지 확인" },
    { key: "employmentInsurance", label: "고용보험 (%)", hint: "안전보건팀 공지 참조. 템플릿 이미지 확인" },
    { key: "indirectRate", label: "간접비 요율 (%)", hint: "윤지민과장에게 문의" },
    { key: "adminRate", label: "일반관리비 요율 (%)", hint: "윤지민과장에게 문의" },
  ];

  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold">설정</h1>
        <p className="text-sm text-muted-foreground mt-1">새 프로젝트 생성 시 자동 적용되는 기본값입니다. 참고 문서에 요율이 있으면 문서 값이 우선 적용됩니다.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">기본 요율</CardTitle>
          <CardDescription>매년 초 변동될 수 있습니다. 인사팀/안전보건팀 공지 확인 후 업데이트하세요.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {fields.map((f) => (
            <div key={f.key} className="space-y-1">
              <label className="text-sm font-medium">{f.label}</label>
              <Input
                type="number"
                step="0.0001"
                value={rates[f.key] || ""}
                onChange={(e) => update(f.key, e.target.value)}
                placeholder="0"
              />
              <span className="text-[11px] text-muted-foreground">{f.hint}</span>
            </div>
          ))}

          <Button onClick={doSave} className="w-full mt-2">
            {saved ? <><Check className="h-4 w-4 mr-2" /> 저장됨</> : <><Save className="h-4 w-4 mr-2" /> 기본값 저장</>}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
