import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { Answers, AnswerValue, Question, Questionnaire } from "../api/types";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { FacesScale } from "./FacesScale";

/** Nota fija bajo cada cuestionario. */
export function QuestionnaireNote() {
  return <p className="questionnaire-note muted" role="note">
    Este cuestionario lo creó su autor. EMOtv no lo valida, no calcula puntajes ni interpreta las respuestas:
    solo las presenta y las registra tal como se dieron.
  </p>;
}

function isEmpty(value: AnswerValue | undefined) {
  return value === undefined || value === "" || (Array.isArray(value) && value.length === 0)
    || (typeof value === "string" && !value.trim());
}

export function missingRequired(questions: Question[], answers: Answers): Question[] {
  return questions.filter((question) => question.required && isEmpty(answers[question.id]));
}

function QuestionField({ question, value, onChange, large }: {
  question: Question;
  value: AnswerValue | undefined;
  onChange?: (value: AnswerValue) => void;
  large: boolean;
}) {
  const name = `q-${question.id}`;
  const legend = <legend>{question.text}{question.required && <span className="required-mark"> (obligatoria)</span>}</legend>;
  if (question.kind === "faces") {
    return <fieldset className="question">{legend}
      <FacesScale name={name} label={question.text} value={typeof value === "number" ? value : null} large={large}
        minLabel={question.min_label} maxLabel={question.max_label} onChange={onChange} />
    </fieldset>;
  }
  if (question.kind === "scale") {
    const points = question.scale_points ?? 5;
    return <fieldset className="question">{legend}
      <div role="radiogroup" aria-label={question.text} className="scale-options">
        {Array.from({ length: points }, (_, index) => index + 1).map((point) =>
          <label key={point} className="scale-option">
            <input type="radio" name={name} checked={value === point} disabled={!onChange}
              aria-label={`${point} de ${points}`} onChange={() => onChange?.(point)} />
            <span aria-hidden="true">{point}</span>
          </label>)}
      </div>
      <div className="scale-ends"><span>{question.min_label}</span><span>{question.max_label}</span></div>
    </fieldset>;
  }
  if (question.kind === "single_choice" || question.kind === "multiple_choice") {
    const multiple = question.kind === "multiple_choice";
    const selected = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
    return <fieldset className="question">{legend}
      {multiple && <p className="muted">Puedes elegir varias.</p>}
      <div className="choice-options">{question.options.map((option) =>
        <label key={option} className="checkbox">
          <input type={multiple ? "checkbox" : "radio"} name={name} checked={selected.includes(option)} disabled={!onChange}
            onChange={(event) => onChange?.(multiple
              ? (event.target.checked ? [...selected, option] : selected.filter((item) => item !== option))
              : option)} />
          <span>{option}</span>
        </label>)}</div>
    </fieldset>;
  }
  return <fieldset className="question">{legend}
    <textarea aria-label={question.text} rows={2} maxLength={500} value={typeof value === "string" ? value : ""}
      disabled={!onChange} onChange={(event) => onChange?.(event.target.value)} />
  </fieldset>;
}

interface QuestionnaireFormProps {
  questionnaire: Pick<Questionnaire, "title" | "instructions" | "questions">;
  /** Sin onSubmit, es una vista previa que no envía nada. */
  onSubmit?: (answers: Answers) => Promise<void> | void;
  submitLabel?: string;
  /** Pantalla de la persona: letra y caritas más grandes, sin datos de la sesión. */
  large?: boolean;
  busy?: boolean;
  footer?: ReactNode;
}

export function QuestionnaireForm({ questionnaire, onSubmit, submitLabel = "Guardar respuestas", large = false, busy = false, footer }: QuestionnaireFormProps) {
  const [answers, setAnswers] = useState<Answers>({});
  const [missing, setMissing] = useState<string[]>([]);

  function change(question: Question, value: AnswerValue) {
    setAnswers((current) => ({ ...current, [question.id]: value }));
    setMissing((current) => current.filter((id) => id !== question.id));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const pending = missingRequired(questionnaire.questions, answers);
    setMissing(pending.map((question) => question.id));
    if (pending.length > 0 || !onSubmit) return;
    const cleaned = Object.fromEntries(Object.entries(answers).filter(([, value]) => !isEmpty(value)));
    await onSubmit(cleaned);
  }

  return <form className={`questionnaire-form${large ? " questionnaire-form-large" : ""}`} onSubmit={(event) => { void submit(event); }}>
    <h2>{questionnaire.title}</h2>
    {questionnaire.instructions && <p>{questionnaire.instructions}</p>}
    {missing.length > 0 && <Callout variant="error">
      Faltan preguntas obligatorias: {questionnaire.questions.filter((item) => missing.includes(item.id)).map((item) => `«${item.text}»`).join(", ")}.
    </Callout>}
    {questionnaire.questions.map((question) => <QuestionField key={question.id} question={question} large={large}
      value={answers[question.id]} onChange={onSubmit ? (value) => change(question, value) : undefined} />)}
    {onSubmit && <Button variant="primary" type="submit" disabled={busy}>{busy ? "Guardando…" : submitLabel}</Button>}
    {footer}
    <QuestionnaireNote />
  </form>;
}

/** Respuestas tal como se dieron: sin sumas, promedios ni interpretación. */
export function AnswerList({ questionnaire, answers }: { questionnaire: Questionnaire; answers: Answers }) {
  return <dl className="answer-list">{questionnaire.questions.map((question) => {
    const value = answers[question.id];
    return <div key={question.id}>
      <dt>{question.text}</dt>
      <dd>{value === undefined ? <span className="muted">Sin respuesta</span> : formatAnswer(question, value)}</dd>
    </div>;
  })}</dl>;
}

function formatAnswer(question: Question, value: AnswerValue): ReactNode {
  if (question.kind === "faces" && typeof value === "number") {
    return <span className="answer-face"><FacesScale name={`a-${question.id}`} label={question.text} value={value}
      minLabel={question.min_label} maxLabel={question.max_label} /> <span>Figura {value} de 5</span></span>;
  }
  if (question.kind === "scale" && typeof value === "number") {
    return `Posición ${value} de ${question.scale_points} (${question.min_label} — ${question.max_label})`;
  }
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}
