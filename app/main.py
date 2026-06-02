import os
import sys

# Forzamos la raíz en el path para evitar problemas de importación en Windows
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app.agent import agent_executor
from langchain_core.messages import HumanMessage, AIMessage

def iniciar_chat_interactivo():
    print("\n========================================================")
    print("      ¡PHARMABOT LOCAL OPERATIVO EN TU PAVILION!       ")
    print("   Consulta stock de medicamentos o valida recetas.   ")
    print("      Escribe 'salir' o 'exit' para terminar.          ")
    print("========================================================\n")
    
    # Lista donde guardaremos la memoria de la conversación actual
    chat_history = []
    
    while True:
        try:
            # Capturamos la entrada del usuario
            user_input = input("Tú: ")
            
            # Condición de salida
            if user_input.lower() in ["salir", "exit", "quit"]:
                print("\nPharmaBot: Entendido. ¡Hasta luego, Gustavo! Cuídate.")
                break
                
            if not user_input.strip():
                continue
                
            # Ejecutamos el agente pasándole la duda y la memoria actual
            # Gracias a verbose=True en agent.py, aquí verás el "pensamiento" de la IA
            response = agent_executor.invoke({
                "input": user_input,
                "chat_history": chat_history
            })
            
            # Imprimimos la respuesta final estructurada de la IA
            print(f"\nPharmaBot: {response['output']}\n")
            print("-" * 50)
            
            # Actualizamos el historial agregando la interacción al formato de LangChain
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=response['output']))
            
        except KeyboardInterrupt:
            print("\n\nPharmaBot: Chat finalizado abruptamente por teclado. ¡Nos vemos!")
            break
        except Exception as e:
            print(f"\n[ERROR] Ocurrió un fallo en el ciclo de ejecución: {e}\n")

if __name__ == "__main__":
    iniciar_chat_interactivo()