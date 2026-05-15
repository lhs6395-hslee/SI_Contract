"use client";

import { useState, useCallback, useEffect, useRef, createContext, useContext } from "react";

// 실제 앱과 동일한 Context 구조 재현
interface TestData {
  extracted: Record<string, { value: string; source: string }>;
}

const TestContext = createContext<{
  data: TestData | null;
  setData: (d: TestData | null | ((prev: TestData | null) => TestData | null)) => void;
} | null>(null);

function useTest() {
  const ctx = useContext(TestContext);
  if (!ctx) throw new Error("no ctx");
  return ctx;
}

// 실제 KVRow와 동일한 패턴
function EditableField({ label, fieldKey, value, source, onChange }: {
  label: string; fieldKey: string; value: string; source: string;
  onChange: (key: string, v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const committed = useRef(false);

  const startEdit = () => {
    committed.current = false;
    setDraft(value);
    setEditing(true);
  };

  const commitEdit = () => {
    if (committed.current) return;
    committed.current = true;
    if (draft !== value) {
      onChange(fieldKey, draft);
    }
    setEditing(false);
  };

  return (
    <div style={{ display: "flex", gap: 12, padding: 8, border: "1px solid #ccc", margin: 4 }}>
      <strong>{label}:</strong>
      {editing ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitEdit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitEdit();
            if (e.key === "Escape") { committed.current = true; setEditing(false); }
          }}
        />
      ) : (
        <span onClick={startEdit} style={{ cursor: "pointer", textDecoration: "underline" }}>
          {value || "(비어있음)"}
        </span>
      )}
      <span style={{ color: "#999", fontSize: 12 }}>{source}</span>
    </div>
  );
}

// 실제 TabBasic과 동일한 패턴
function FieldEditor() {
  const { data, setData } = useTest();
  const E = data?.extracted || {};

  const updateField = useCallback((key: string, newValue: string) => {
    console.log(`[updateField] key=${key}, newValue=${newValue}`);
    setData((prev) => {
      if (!prev) return prev;
      console.log(`[updater] prev.${key}.value = ${prev.extracted[key]?.value}`);
      const result = {
        ...prev,
        extracted: {
          ...prev.extracted,
          [key]: { value: newValue, source: "수동 수정" },
        },
      };
      console.log(`[updater] result.${key}.value = ${result.extracted[key]?.value}`);
      return result;
    });
  }, [setData]);

  return (
    <div>
      <EditableField label="PM" fieldKey="pm" value={E.pm?.value || ""} source={E.pm?.source || ""} onChange={updateField} />
      <EditableField label="발주처" fieldKey="client" value={E.client?.value || ""} source={E.client?.source || ""} onChange={updateField} />
      <EditableField label="매출" fieldKey="revenue" value={E.revenue?.value || ""} source={E.revenue?.source || ""} onChange={updateField} />
    </div>
  );
}

// 실제 page.tsx와 동일한 패턴
export default function TestPage() {
  const [data, setDataState] = useState<TestData | null>({
    extracted: {
      pm: { value: "강서원", source: "AI 추출" },
      client: { value: "삼성전자", source: "AI 추출" },
      revenue: { value: "676800000", source: "AI 추출" },
    },
  });

  // 실제 앱의 setExtractedDataWrapped와 동일
  const setDataWrapped = useCallback(
    (input: TestData | null | ((prev: TestData | null) => TestData | null)) => {
      if (typeof input === "function") {
        setDataState(input);
      } else {
        setDataState(input);
      }
    },
    [],
  );

  // 실제 앱과 동일: projects state + localStorage 저장
  const [projects, setProjects] = useState([{ id: "p1", name: "테스트" }]);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!data) return;
    console.log("[useEffect] data changed, pm =", data.extracted.pm?.value);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      console.log("[save] saving to localStorage & updating projects");
      // localStorage 저장 시뮬레이션
      localStorage.setItem("test_data", JSON.stringify(data));
      // setProjects 호출 (실제 앱과 동일)
      setProjects((prev) => {
        const copy = [...prev];
        copy[0] = { ...copy[0], name: data.extracted.pm?.value || "테스트" };
        return copy;
      });
    }, 100);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [data]);

  return (
    <TestContext value={{ data, setData: setDataWrapped }}>
      <div style={{ padding: 40, fontFamily: "sans-serif" }}>
        <h1>Context 체인 테스트</h1>
        <p>실제 앱과 동일한 Context → useCallback → 함수형 업데이트 체인</p>
        <FieldEditor />
        <pre style={{ marginTop: 20, background: "#f5f5f5", padding: 12 }}>
          현재 state: {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    </TestContext>
  );
}
