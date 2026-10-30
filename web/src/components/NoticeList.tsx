import { useState } from "react";
import { apiRequest } from "../api/http";
import type { UserNotice } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "./Button";
import { Callout } from "./Callout";

/** Avisos de la cuenta (imágenes eliminadas o por vencer, protocolos que necesitan una imagen). */
export function NoticeList() {
  const { token } = useAuth();
  const query = useApiQuery<UserNotice[]>("/notices");
  const [hidden, setHidden] = useState<string[]>([]);
  const items = (query.data ?? []).filter((item) => !hidden.includes(item.id));
  if (items.length === 0) return null;

  async function dismiss(id: string) {
    setHidden((current) => [...current, id]);
    try { await apiRequest(`/notices/${encodeURIComponent(id)}/read`, { method: "POST", token }); }
    catch { setHidden((current) => current.filter((item) => item !== id)); }
  }

  return <div className="notice-list">
    {items.map((item) => <Callout key={item.id} variant="warning" className="notice-item">
      <span>{item.message}</span>
      <Button size="sm" variant="ghost" onClick={() => { void dismiss(item.id); }}>Entendido</Button>
    </Callout>)}
  </div>;
}
