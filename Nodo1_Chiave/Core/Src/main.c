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
 * DEVE essere IDENTICA nel Nodo 2.
 * In un sistema reale verrebbe protetta in Flash OTP o TrustZone;
 * qui e' hardcoded a scopo dimostrativo.
 */
static const uint8_t shared_key[16] = {
    0x2B, 0x7E, 0x15, 0x16,
    0x28, 0xAE, 0xD2, 0xA6,
    0xAB, 0xF7, 0x15, 0x88,
    0x09, 0xCF, 0x4F, 0x3C
};

/*
 * Costante "OPEN" codificata come 4 byte.
 * Inserita nel plaintext come sanity-check post-decifratura sul Nodo 2.
 * 'O'=0x4F 'P'=0x50 'E'=0x45 'N'=0x4E
 */
#define CMD_OPEN_WORD  0x4F50454Eul

/* Padding fisso per completare il blocco da 16 byte (byte 8..15) */
#define PADDING_BYTE   0xAA

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
CRC_HandleTypeDef hcrc;

UART_HandleTypeDef huart1;
DMA_HandleTypeDef hdma_usart1_tx;

/* USER CODE BEGIN PV */

char tx_buffer[PACKET_SIZE + 1]; // Per la Chiave
uint32_t key_counter = 0; // Il nostro contatore di sicurezza

/*
 * Flag di modalita' operativa, commutabile a runtime dal pulsante:
 *   0 = Scenario 1 (Fase 1, pacchetto in chiaro)
 *   1 = Scenario 2 (Fase 2, pacchetto cifrato con AES-128-ECB)
 * Deve essere tenuto sincronizzato manualmente con il Nodo 2.
 */
uint8_t secure_mode = 0;

/* Buffer di lavoro per la cifratura AES (Fase 2) */
static uint8_t plaintext[AES_BLOCK_SIZE];
static uint8_t ciphertext[AES_BLOCK_SIZE];

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_CRC_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

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
  MX_CRC_Init();
  /* USER CODE BEGIN 2 */

  /*
   * Inizializzazione della libreria X-CUBE-CRYPTOLIB.
   * Deve essere chiamata una sola volta prima di qualsiasi
   * operazione crittografica. Necessaria anche in Fase 1
   * (nessun overhead: se secure_mode==0 non viene mai usata).
   */
  cmox_initialize(NULL);

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
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
  /* DMA1_Channel4_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA1_Channel4_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(DMA1_Channel4_IRQn);

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
  HAL_GPIO_WritePin(GPIOE, Blue_Led_Pin|Red_Led_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : User_button_Pin */
  GPIO_InitStruct.Pin = User_button_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(User_button_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : send_button_Pin */
  GPIO_InitStruct.Pin = send_button_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING_FALLING;
  GPIO_InitStruct.Pull = GPIO_PULLUP;
  HAL_GPIO_Init(send_button_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : Blue_Led_Pin Red_Led_Pin */
  GPIO_InitStruct.Pin = Blue_Led_Pin|Red_Led_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI0_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI0_IRQn);

  HAL_NVIC_SetPriority(EXTI1_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI1_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    /* ─────────────────────────────────────────────────────────────────────────

     * 1. PULSANTE ONBOARD (GPIO_PIN_0) -> SWITCH MODALITÀ (Safe / Secure)

     * ───────────────────────────────────────────────────────────────────────── */
    if (GPIO_Pin == GPIO_PIN_0)
    {
        uint32_t now = HAL_GetTick();
        static uint32_t last_press_mode = 0;
        // Anti-rimbalzo (Debounce) dedicato alla modalità
        if ((now - last_press_mode) < 200) return;
        last_press_mode = now;
        secure_mode = !secure_mode;
        /*

         * Al cambio di modalità azzera il contatore di trasmissione.

         * Questo permette a Nodo 1 e Nodo 2 di ripartire da zero insieme

         * e rimanere perfettamente sincronizzati.

         */

        key_counter = 0;

        // Feedback visivo: invertiamo il LED arancione/blu (es. PE8) per indicare il cambio

        HAL_GPIO_TogglePin(GPIOE, GPIO_PIN_8);
    }
    /* ─────────────────────────────────────────────────────────────────────────

     * 2. NUOVO PULSANTE ESTERNO (Es. GPIO_PIN_1) -> TRASMISSIONE COMANDO

     * ─────────────────────────────────────────────────────────────────────────

     * NOTA: Sostituisci "GPIO_PIN_1" con il pin esatto che hai scelto su CubeMX

     * (ad esempio GPIO_PIN_3, GPIO_PIN_4, ecc.)

     * ───────────────────────────────────────────────────────────────────────── */
    else if (GPIO_Pin == GPIO_PIN_1)
    {
        uint32_t now = HAL_GetTick();
        static uint32_t  last_edge_time  = 0;
        static uint8_t   button_pressed  = 0;   // <-- flag "già premuto"

        /* Debounce rapido su qualsiasi fronte (50 ms bastano per il rumore) */
        if ((now - last_edge_time) < 50) return;
        last_edge_time = now;

        /* Leggiamo lo stato reale del pin subito dopo il fronte */
        GPIO_PinState state = HAL_GPIO_ReadPin(send_button_GPIO_Port, send_button_Pin);

        if (state == GPIO_PIN_RESET)
        {
            /* ── FRONTE DI DISCESA: pulsante appena premuto ─── */
            if (button_pressed) return;   // già tenuto: ignora assolutamente
            button_pressed = 1;

            key_counter++;

            if (secure_mode == 0)
            {
                /* ── FASE 1: pacchetto in chiaro ─── */
                snprintf(tx_buffer, sizeof(tx_buffer),
                         "OPEN:1234:CNT:%04lu\n", key_counter);
            }
            else
            {
                /* ── FASE 2: pacchetto cifrato AES-128-ECB ─── */
                memset(plaintext, 0, AES_BLOCK_SIZE);

                plaintext[0] = (uint8_t)( key_counter        & 0xFF);
                plaintext[1] = (uint8_t)((key_counter >>  8) & 0xFF);
                plaintext[2] = (uint8_t)((key_counter >> 16) & 0xFF);
                plaintext[3] = (uint8_t)((key_counter >> 24) & 0xFF);

                plaintext[4] = (uint8_t)((CMD_OPEN_WORD >> 24) & 0xFF);
                plaintext[5] = (uint8_t)((CMD_OPEN_WORD >> 16) & 0xFF);
                plaintext[6] = (uint8_t)((CMD_OPEN_WORD >>  8) & 0xFF);
                plaintext[7] = (uint8_t)( CMD_OPEN_WORD        & 0xFF);

                memset(&plaintext[8], PADDING_BYTE, 8);

                size_t output_len = 0;
                cmox_cipher_retval_t retval = cmox_cipher_encrypt(
                    CMOX_AESFAST_ECB_ENC_ALGO,
                    plaintext, AES_BLOCK_SIZE,
                    shared_key, 16,
                    NULL, 0,
                    ciphertext, &output_len);

                if (retval != CMOX_CIPHER_SUCCESS) return;

                for (int i = 0; i < AES_BLOCK_SIZE; i++)
                    snprintf(&tx_buffer[i * 2], 3, "%02X", ciphertext[i]);
            }

            HAL_UART_Transmit_DMA(&huart1, (uint8_t*)tx_buffer, PACKET_SIZE);
            HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9, GPIO_PIN_SET);  // LED TX ON
        }
        else
        {
            /* ── FRONTE DI SALITA: pulsante rilasciato ─── */
            button_pressed = 0;   // ora una nuova pressione sarà accettata
        }
    }
}
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)

{
    // Spegne il LED di trasmissione al completamento del DMA
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_9, GPIO_PIN_RESET);
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
