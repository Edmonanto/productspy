"use client";

import { useEffect } from "react";
import { partnersApi } from "@/lib/api";
import { readRef, writeRef } from "./RefCapture";

/** In the dashboard: once signed in, hand a remembered partner code to the server once. */
export default function AttachRef() {
  useEffect(() => {
    const ref = readRef();
    if (!ref || ref.sent) return;
    partnersApi.attribute(ref.code)
      .then(() => writeRef({ ...ref, sent: true }))   // ok or refused: either way, don't retry
      .catch(() => {});                                 // network error: try again next visit
  }, []);
  return null;
}
