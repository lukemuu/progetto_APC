/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "cmox_crypto.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define PACKET_SIZE     32
#define AES_BLOCK_SIZE  16
#define CMOX_AES_IMPL CMOX_AES_SMALL

/*
 * Chiave AES-128 condivisa (16 byte).
 * DEVE essere IDENTICA a quella nel Nodo 1.
 */
static const uint8_t shared_key[16] = {
    0x2B, 0x7E, 0x15, 0x16,
    0x28, 0xAE, 0xD2, 0xA6,
    0xAB, 0xF7, 0x15, 0x88,
    0x09, 0xCF, 0x4F, 0x3C
};

/* Stessa costante usata dal Nodo 1 per il sanity-check post-decifratura */
#define CMD_OPEN_WORD  0x4F50454Eul

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
CRC_HandleTypeDef hcrc;

TIM_HandleTypeDef htim2;

UART_HandleTypeDef huart1;
DMA_HandleTypeDef hdma_usart1_rx;

/* USER CODE BEGIN PV */

uint8_t rx_buffer[PACKET_SIZE + 1]; // Per la Serratura
uint8_t secure_mode = 0;       // 0 = Scenario 1 (Insicuro), 1 = Scenario 2 (Sicuro)
uint32_t last_valid_counter = 0; // Memoria dell'ultimo contatore accettato

volatile uint8_t access_event = 0; // 0=nessuno, 1=corretto, 2=errato

/* Buffer di lavoro interni alla callback (Fase 2) */
static uint8_t ciphertext_bin[AES_BLOCK_SIZE];
static uint8_t decrypted[AES_BLOCK_SIZE];

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_TIM2_Init(void);
static void MX_CRC_Init(void);
/* USER CODE BEGIN PFP */
static uint8_t hex_char_to_nibble(char c);
static int hex_to_bytes(const uint8_t *hex_str, uint8_t *out, uint16_t out_len);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/**
  * @brief  Converte un singolo carattere hex ASCII nel suo valore nibble.
  *         Restituisce 0xFF se il carattere non e' hex valido.
  *         Esempi: '0'->0x0, '9'->0x9, 'A'->0xA, 'f'->0xF
  */
static uint8_t hex_char_to_nibble(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
    if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
    if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
    return 0xFF;
}

/**
  * @brief  Converte una stringa ASCII hex in un array di byte binari.
  * @param  hex_str  Stringa di input (es. "A3F7C2B1..."), 2*out_len caratteri
  * @param  out      Buffer di output
  * @param  out_len  Numero di byte da produrre (= lunghezza stringa / 2)
  * @retval 0 = successo, -1 = carattere non valido trovato
  *
  * Esempio: "A3F7" (4 char) -> {0xA3, 0xF7} (2 byte)
  */
static int hex_to_bytes(const uint8_t *hex_str, uint8_t *out, uint16_t out_len)
{
    for (uint16_t i = 0; i < out_len; i++)
    {
        uint8_t hi = hex_char_to_nibble((char)hex_str[i * 2]);
        uint8_t lo = hex_char_to_nibble((char)hex_str[i * 2 + 1]);

        if (hi == 0xFF || lo == 0xFF)
        {
            return -1;
        }

        out[i] = (uint8_t)((hi << 4) | lo);
    }
    return 0;
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART1_UART_Init();
  MX_TIM2_Init();
  MX_CRC_Init();
  /* USER CODE BEGIN 2 */

  /*
   * Inizializzazione della libreria X-CUBE-CRYPTOLIB.
   * Deve essere chiamata una sola volta prima di qualsiasi
   * operazione crittografica.
   */
  cmox_initialize(NULL);

  HAL_UART_Receive_DMA(&huart1, rx_buffer, PACKET_SIZE);

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
      /* USER CODE BEGIN WHILE */

      // --- CASO 1: APERTURA AUTORIZZATA ---
      if (access_event == 1)
      {
          access_event = 0; // Resetta immediatamente il flag per non ciclare

          // LED Verde ON per 1 secondo (Sblocco Solenoide/Relè)
          HAL_GPIO_WritePin(GPIOE, GPIO_PIN_15, GPIO_PIN_SET);
          HAL_Delay(1000);
          HAL_GPIO_WritePin(GPIOE, GPIO_PIN_15, GPIO_PIN_RESET);
      }

      // --- CASO 2: ACCESSO NEGATO / ATTACCO IN CORSO ---
      else if (access_event == 2)
      {
          access_event = 0; // Resetta immediatamente il flag

          // 5 lampeggi LED Rosso + Buzzer passivo sul Canale 2 (PA1)
          for (int i = 0; i < 5; i++)
          {
              HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9, GPIO_PIN_SET);
              HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2); // <--- Canale 2 aggiornato!
              HAL_Delay(200); // 200ms acceso per un effetto allarme più dinamico

              HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9, GPIO_PIN_RESET);
              HAL_TIM_PWM_Stop(&htim2, TIM_CHANNEL_2);  // <--- Canale 2 aggiornato!
              HAL_Delay(200); // 200ms spento
          }
      }
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL6;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
  {
    Error_Handler();
  }
  PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_USART1;
  PeriphClkInit.Usart1ClockSelection = RCC_USART1CLKSOURCE_PCLK2;
  if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief CRC Initialization Function
  * @param None
  * @retval None
  */
static void MX_CRC_Init(void)
{

  /* USER CODE BEGIN CRC_Init 0 */

  /* USER CODE END CRC_Init 0 */

  /* USER CODE BEGIN CRC_Init 1 */

  /* USER CODE END CRC_Init 1 */
  hcrc.Instance = CRC;
  hcrc.Init.DefaultPolynomialUse = DEFAULT_POLYNOMIAL_ENABLE;
  hcrc.Init.DefaultInitValueUse = DEFAULT_INIT_VALUE_ENABLE;
  hcrc.Init.InputDataInversionMode = CRC_INPUTDATA_INVERSION_NONE;
  hcrc.Init.OutputDataInversionMode = CRC_OUTPUTDATA_INVERSION_DISABLE;
  hcrc.InputDataFormat = CRC_INPUTDATA_FORMAT_BYTES;
  if (HAL_CRC_Init(&hcrc) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN CRC_Init 2 */

  /* USER CODE END CRC_Init 2 */

}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 23;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 999;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 499;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */
  HAL_TIM_MspPostInit(&htim2);

}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 9600;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  huart1.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * Enable DMA controller clock
  */
static void MX_DMA_Init(void)
{

  /* DMA controller clock enable */
  __HAL_RCC_DMA1_CLK_ENABLE();

  /* DMA interrupt init */
  /* DMA1_Channel5_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA1_Channel5_IRQn, 5, 0);
  HAL_NVIC_EnableIRQ(DMA1_Channel5_IRQn);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOE_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOE, Blue_Led_Pin|Red_Led_Pin|Green_Led_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : switch_mode_Pin */
  GPIO_InitStruct.Pin = switch_mode_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(switch_mode_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : Blue_Led_Pin Red_Led_Pin Green_Led_Pin */
  GPIO_InitStruct.Pin = Blue_Led_Pin|Red_Led_Pin|Green_Led_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI0_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI0_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == GPIO_PIN_0)
    {
        uint32_t now = HAL_GetTick();
        static uint32_t last_press = 0;

        if ((now - last_press) < 200) return;
        last_press = now;

        secure_mode = !secure_mode;

        /*
         * Al cambio di modalita' azzera il contatore di riferimento.
         * Questo e' necessario perche' il Nodo 1 resetta key_counter
         * al suo switch: i due nodi devono ripartire da zero insieme.
         */
        last_valid_counter = 0;

        HAL_GPIO_TogglePin(GPIOE, GPIO_PIN_8);
    }
}


void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        // 1. Il comando base è corretto?
        if (strstr((char*)rx_buffer, "OPEN:1234") != NULL)
        {
            // --- SCENARIO 1: SISTEMA IN CHIARO / VULNERABILE ---
            if (secure_mode == 0)
            {
                access_event = 1; // Apri sempre, ignora il contatore!
            }
            // --- SCENARIO 2: SISTEMA SICURO CON ROLLING CODE ---
            else
            {
                uint32_t received_counter = 0;
                char *cnt_ptr = strstr((char*)rx_buffer, ":CNT:");

                if (cnt_ptr != NULL)
                {
                    received_counter = strtoul(cnt_ptr + 5, NULL, 10);
                }

                // Verifica del contatore rolling code
                if (received_counter > last_valid_counter)
                {
                    last_valid_counter = received_counter; // Aggiorna la memoria
                    access_event = 1;                      // Accesso Consentito!
                }
                else
                {
                    access_event = 2; // REPLAY ATTACK RILEVATO! (Contatore vecchio o doppio)
                }
            }
        }
        else
        {
            /* ── FASE 2: pacchetto cifrato ───────────────────────────────
             *
             * Il pacchetto non contiene "OPEN:1234" in chiaro: e' un
             * pacchetto cifrato con AES-128-ECB proveniente dalla Fase 2
             * del Nodo 1. Viene elaborato solo se secure_mode == 1.
             * Se secure_mode == 0 e arriva un pacchetto cifrato, e' errato.
             */
            if (secure_mode == 0)
            {
                access_event = 2;
                goto rearm_dma;
            }

            /* STEP 1 — decodifica hex ASCII -> binario:
             * rx_buffer contiene 32 caratteri ASCII (es. "A3F7C2B1...").
             * hex_to_bytes() li converte nei 16 byte binari cifrati.
             */
            if (hex_to_bytes(rx_buffer, ciphertext_bin, AES_BLOCK_SIZE) != 0)
            {
                access_event = 2;
                goto rearm_dma;
            }

            /* STEP 2 — decifratura AES-128-ECB:
             * Stessa chiave del Nodo 1. Produce 16 byte di plaintext.
             */
            size_t output_len = 0;
            cmox_cipher_retval_t retval = cmox_cipher_decrypt(
                CMOX_AESFAST_ECB_DEC_ALGO, // Il nuovo identificativo dell'algoritmo di decifratura
                ciphertext_bin,            // Buffer con i 16 byte cifrati ricevuti
                AES_BLOCK_SIZE,            // Lunghezza dei dati cifrati (16 byte)
                shared_key,                // La tua chiave AES (deve essere identica a quella del Nodo 1)
                16,                        // Dimensione della chiave espressa in byte (16)
                NULL,                      // IV (Impostato a NULL per ECB)
                0,                         // Lunghezza dell'IV (0)
                decrypted,                 // Buffer in cui salvare il testo in chiaro decifrato
                &output_len                // Variabile che conterrà il numero di byte scritti
            );

            if (retval != CMOX_CIPHER_SUCCESS)
            {
                access_event = 2;
                goto rearm_dma;
            }

            /* STEP 3 — sanity-check sul campo "command" (byte 4..7):
             * Verifica che il plaintext decifrato contenga CMD_OPEN_WORD.
             * Se la chiave fosse sbagliata o il pacchetto corrotto,
             * questo confronto fallirebbe.
             */
            uint32_t received_cmd =
                ((uint32_t)decrypted[4] << 24) |
                ((uint32_t)decrypted[5] << 16) |
                ((uint32_t)decrypted[6] <<  8) |
                ((uint32_t)decrypted[7]);

            if (received_cmd != CMD_OPEN_WORD)
            {
                access_event = 2;
                goto rearm_dma;
            }

            /* STEP 4 — estrazione del counter (byte 0..3, little-endian) */
            uint32_t received_counter =
                ((uint32_t)decrypted[0])       |
                ((uint32_t)decrypted[1] <<  8) |
                ((uint32_t)decrypted[2] << 16) |
                ((uint32_t)decrypted[3] << 24);

            /* STEP 5 — Rolling Code check:
             * Il contatore e' valido solo se strettamente maggiore
             * dell'ultimo accettato. Uguale o minore = Replay Attack.
             */
            if (received_counter > last_valid_counter)
            {
                last_valid_counter = received_counter;
                access_event = 1; // Accesso Consentito!
            }
            else
            {
                access_event = 2; // REPLAY ATTACK RILEVATO!
            }
        }

rearm_dma:
        // Pulisci e riarma il DMA immediatamente
        memset(rx_buffer, 0, sizeof(rx_buffer));
        HAL_UART_Receive_DMA(huart, rx_buffer, PACKET_SIZE);
    }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
