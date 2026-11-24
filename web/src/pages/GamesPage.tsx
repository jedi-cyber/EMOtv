import { ButtonLink } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { paths } from "../routes/paths";

/**
 * Juegos: la actividad de dibujo y una versión de prueba de cada juego. Nada de
 * esto crea una sesión, usa la cámara ni guarda datos. En una sesión, los juegos
 * se agregan a un protocolo y usan imágenes aprobadas.
 */
export function GamesPage() {
  return <section>
    <PageHeader title="Juegos" description="Prueba los juegos antes de ponerlos en un protocolo. Aquí no se crea una sesión, no se usa la cámara y no se guarda nada." />
    <div className="card-grid">
      <article className="card">
        <h2>Dibuja una cara</h2>
        <p>Elige imágenes para que la persona dibuje una cara a partir de cada una, o dibuja sin imagen. No crea una sesión, no usa la cámara y no guarda el dibujo.</p>
        <ButtonLink variant="primary" to={paths.drawing}>Actividad de dibujo</ButtonLink>
      </article>
      <article className="card">
        <h2>Empareja la emoción</h2>
        <p>Se muestra una cara y la persona elige el nombre de su emoción. Versión de prueba de tres rondas, con caras dibujadas.</p>
        <ButtonLink variant="primary" to={paths.game("matching")}>Jugar la prueba</ButtonLink>
      </article>
      <article className="card">
        <h2>Busca la misma emoción</h2>
        <p>Se muestra una cara arriba y la persona busca, entre otras caras, la que muestra la misma emoción. Versión de prueba de tres rondas.</p>
        <ButtonLink variant="primary" to={paths.game("similar")}>Jugar la prueba</ButtonLink>
      </article>
    </div>
  </section>;
}
