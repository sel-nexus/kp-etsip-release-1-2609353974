import { RouterProvider } from 'react-router-dom';
import { router } from './routes';

/** Render the application through its single configured router. */
export default function App(): JSX.Element {
  return <RouterProvider router={router} />;
}
